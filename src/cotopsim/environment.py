import numpy as np
import random
import math
from cotopsim.task        import Task
from cotopsim.vehicle     import Vehicle
from cotopsim.rsu         import RSU
from cotopsim.channel     import Channel
from cotopsim.computation import ComputationModel
from cotopsim.priority    import PriorityAlgorithm

class CoToPEnvironment:

    # ── Constants ─────────────────────────────────────────────
    NUM_RSUS        = 6
    ROAD_LENGTH     = 200.0
    COVERAGE_RADIUS = 400.0
    RSU_CAPACITY    = 2000.0   # Mcycles/s
    MAX_TASKS       = 3        # I — max tasks per slot
    STATE_DIM       = 21
    ACTION_DIM      = 7        # 0=standalone, 1-6=collaborate
    PENALTY_Z       = 10.0

    # Normalisation constants
    NORM_X          = 200.0
    NORM_SPEED      = 40.0
    NORM_SIZE       = 40.0     # Mbits
    NORM_CPU        = 10.0     # Mcycles
    NORM_DEADLINE   = 30.0     # seconds
    NORM_PRIORITY   = 3.0
    NORM_QUEUE      = 50.0     # Mcycles

    def __init__(self,
                 num_vehicles = 1,
                 max_steps    = 50,
                 sigma        = 0.3,   # delay/energy weight
                 seed         = 42):
        self.num_vehicles = num_vehicles
        self.max_steps    = max_steps
        self.sigma        = sigma      # Eq. 13 weight
        self.seed         = seed

        # ── Build RSUs ────────────────────────────────────────
        spacing = self.ROAD_LENGTH / self.NUM_RSUS
        self.rsus = {}
        for i in range(1, self.NUM_RSUS + 1):
            x            = spacing * (i - 0.5)
            neighbor_ids = []
            if i > 1: neighbor_ids.append(i - 1)
            if i < self.NUM_RSUS: neighbor_ids.append(i + 1)
            self.rsus[i] = RSU(
                rsu_id          = i,
                x               = x,
                capacity        = self.RSU_CAPACITY,
                coverage_radius = self.COVERAGE_RADIUS,
                neighbor_ids    = neighbor_ids
            )
        # Link neighbors
        for rsu in self.rsus.values():
            rsu.neighbors = {
                nid: self.rsus[nid]
                for nid in rsu.neighbor_ids
            }

        # ── Build channel and models ──────────────────────────
        self.channel    = Channel()
        self.comp_model = ComputationModel()
        self.priority   = PriorityAlgorithm(alpha=0.3, beta=0.7)

        # ── Episode state ─────────────────────────────────────
        self.vehicles    = []
        self.step_count  = 0
        self.all_tasks   = []
        self.episode_metrics = {
            'total_delay' : 0.0,
            'total_energy': 0.0,
            'completed'   : 0,
            'failed'      : 0,
            'generated'   : 0
        }

    def _make_vehicle(self, vid):
        x     = random.uniform(0, self.ROAD_LENGTH)
        speed = random.uniform(30.0, 40.0)
        return Vehicle(vehicle_id=vid, x=x, speed=speed)

    def reset(self):
        """Reset environment. Returns initial state vector."""
        random.seed(self.seed + self.step_count)

        # Reset RSUs
        for rsu in self.rsus.values():
            rsu.reset()

        # Reset vehicles
        self.vehicles = [
            self._make_vehicle(i+1)
            for i in range(self.num_vehicles)
        ]

        self.step_count = 0
        self.all_tasks  = []
        self.episode_metrics = {
            'total_delay' : 0.0,
            'total_energy': 0.0,
            'completed'   : 0,
            'failed'      : 0,
            'generated'   : 0
        }

        return self._get_state()

    def _get_state(self):
        """
        Build 20-dimensional state vector.
        s(t) = [s_v, s_task, s_RSU]
        """
        v = self.vehicles[0]   # Phase 1: single vehicle

        # Vehicle features (3) — add dwell time
        serving_rsu = self._find_serving_rsu(v)
        t_stay = v.estimate_dwell_time(serving_rsu) if serving_rsu else 0.0

        sv = [
            v.x     / self.NORM_X,
            v.speed / self.NORM_SPEED,
            min(t_stay, 30.0) / 30.0   # normalize dwell time
        ]

        # Task features (12) — pad with zeros if < 3 tasks
        pending = [t for t in self.all_tasks
                   if t.status == Task.STATUS_PENDING][:self.MAX_TASKS]

        s_task = []
        for task in pending:
            s_task.extend([
                task.size       / self.NORM_SIZE,
                task.cpu_cycles / self.NORM_CPU,
                task.deadline   / self.NORM_DEADLINE,
                task.priority   / self.NORM_PRIORITY
            ])
        # Pad missing tasks with zeros
        while len(s_task) < self.MAX_TASKS * 4:
            s_task.extend([0.0, 0.0, 0.0, 0.0])

        # RSU features (6) — queue load per RSU
        s_rsu = [
            rsu.queued_cycles() / self.NORM_QUEUE
            for rsu in self.rsus.values()
        ]

        state = sv + s_task + s_rsu
        assert len(state) == self.STATE_DIM, \
            f"State dim mismatch: {len(state)} != {self.STATE_DIM}"
        return np.array(state, dtype=np.float32)
    def step(self, action, current_task=None):
        
        self.step_count += 1

        # ── Get current vehicle and task ──────────────────────
        v = self.vehicles[0]

        if current_task is None:
            pending = [t for t in self.all_tasks
                       if t.status == Task.STATUS_PENDING]
            if not pending:
                return self._get_state(), 0.0, True, {}
            current_task = pending[0]

        # ── Find serving RSU ──────────────────────────────────
        serving_rsu = self._find_serving_rsu(v)
        if serving_rsu is None:
            # No RSU in range — task fails
            current_task.status = Task.STATUS_FAILED
            self.episode_metrics['failed'] += 1
            reward = -self.PENALTY_Z
            return self._get_state(), reward, self._is_done(), {
                'reason': 'no_rsu_in_range'
            }

        # ── Estimate dwell time ───────────────────────────────
        t1 = v.estimate_dwell_time(serving_rsu)

        # ── Execute action ────────────────────────────────────
        if action == 0:
            rsu_target = serving_rsu
        else:
            rsu_target = self.rsus.get(action, serving_rsu)

        delay  = self.comp_model.total_standalone_delay(
            current_task, v, rsu_target, self.channel)
        energy = self.comp_model.total_energy(current_task)
        current_task.assigned_rsu_id = rsu_target.rsu_id
        current_task.source_rsu_id   = serving_rsu.rsu_id
        rsu_target.accept_task(current_task,
                            arrival_time=self.step_count)
        # ── Compute reward (Eq. 25) ───────────────────────────
        if delay > current_task.deadline:
            reward = -self.PENALTY_Z
            current_task.status = Task.STATUS_FAILED
            self.episode_metrics['failed'] += 1
        else:
            reward = -(self.sigma * delay +
                       (1 - self.sigma) * energy)
            current_task.status = Task.STATUS_COMPLETED
            self.episode_metrics['completed'] += 1

        # ── Update episode metrics ────────────────────────────
        self.episode_metrics['total_delay']  += delay
        self.episode_metrics['total_energy'] += energy

        # ── Move vehicle and tick RSUs ────────────────────────
        v.move(dt=1.0)
        for rsu in self.rsus.values():
            rsu.tick(dt=1.0)
            rsu.completed_tasks.clear()

        return self._get_state(), reward, self._is_done(), {
            'delay'        : delay,
            'energy'       : energy,
            'action'       : action,
            'deadline_met' : delay <= current_task.deadline,
            'serving_rsu'  : serving_rsu.rsu_id
        }

    def _find_serving_rsu(self, vehicle):
        """Find RSU with shortest queue among those in range."""
        candidates = [
            rsu for rsu in self.rsus.values()
            if rsu.in_range(vehicle)
        ]
        if not candidates:
            return None
        return min(candidates,
                   key=lambda r: r.queued_cycles())

    def _is_done(self):
        """Episode ends after max_steps or all tasks processed."""
        all_done = all(
            t.status in (Task.STATUS_COMPLETED, Task.STATUS_FAILED)
            for t in self.all_tasks
        )
        return self.step_count >= self.max_steps or all_done

    def generate_episode_tasks(self, target_tasks=25):
        """Pre-generate tasks for one episode (paper: 20-40 tasks)."""
        self.all_tasks = []
        v = self.vehicles[0]
        while len(self.all_tasks) < target_tasks:
            tasks = v.generate_tasks(current_time=len(self.all_tasks))
            self.all_tasks.extend(tasks)
        self.all_tasks = self.all_tasks[:target_tasks]  # trim to exact count
        self.episode_metrics['generated'] = len(self.all_tasks)

        # Compute priorities
        t_stay = v.estimate_dwell_time(
            list(self.rsus.values())[2]  # reference RSU 3
        )
        t_stay_map = {t.task_id: t_stay for t in self.all_tasks}
        self.priority.sort_tasks(self.all_tasks, t_stay_map)
        return self.all_tasks

    def get_metrics(self):
        pending   = sum(1 for t in self.all_tasks
                        if t.status == Task.STATUS_PENDING)
        completed = self.episode_metrics['completed']
        failed    = self.episode_metrics['failed'] + pending
        generated = self.episode_metrics['generated']

        return {
            'avg_delay'       : self.episode_metrics['total_delay'] /
                                max(completed, 1),
            'avg_energy'      : self.episode_metrics['total_energy'] /
                                max(completed, 1),
            'completion_ratio': completed / max(generated, 1),
            'completed'       : completed,
            'failed'          : failed,
            'pending'         : pending,
            'generated'       : generated
        }

    def __repr__(self):
        return (f"CoToPEnvironment | "
                f"vehicles={self.num_vehicles} | "
                f"RSUs={self.NUM_RSUS} | "
                f"steps={self.step_count}/{self.max_steps}")

if __name__ == "__main__":
    import random
    random.seed(42)
    np.random.seed(42)

    print("=== Sprint 9: Environment Verification ===")

    env = CoToPEnvironment(num_vehicles=1, max_steps=50, seed=42)
    print(f"\n{env}")

    # ── Test 1: Reset ─────────────────────────────────────────
    print("\n--- Reset test ---")
    state = env.reset()
    print(f"State shape:    {state.shape}  (expect (20,))")
    print(f"State min/max:  {state.min():.3f} / {state.max():.3f}")
    print(f"Vehicle pos:    x={env.vehicles[0].x:.1f}m  "
          f"speed={env.vehicles[0].speed:.1f}m/s")

    # ── Test 2: Generate tasks ────────────────────────────────
    print("\n--- Task generation ---")
    tasks = env.generate_episode_tasks(target_tasks=5)
    # tasks = env.generate_episode_tasks(num_tasks=5)  # just 5
    print(f"Generated {len(tasks)} tasks")
    print(f"Top 3 by priority:")
    for t in tasks[:3]:
        print(f"  {t.task_id}: size={t.size:.1f}Mb "
              f"deadline={t.deadline:.1f}s "
              f"priority={t.priority:.4f}")

    # ── Test 3: Single step ───────────────────────────────────
    print("\n--- Single step test ---")
    env3 = CoToPEnvironment(num_vehicles=1, max_steps=50, seed=42)
    state = env3.reset()
    tasks = env3.generate_episode_tasks(target_tasks=5)
    task = tasks[0]
    print(f"Scheduling: {task.task_id} "
          f"size={task.size:.1f}Mb deadline={task.deadline:.1f}s")

    next_state, reward, done, info = env3.step(action=0, 
                                               current_task=task)
    print(f"Action:      0 (standalone)")
    print(f"Reward:      {reward:.4f}")
    print(f"Done:        {done}")
    print(f"Delay:       {info['delay']:.4f}s")
    print(f"Energy:      {info['energy']:.4f}J")
    print(f"Deadline met:{info['deadline_met']}")
    print(f"Serving RSU: {info['serving_rsu']}")

    # ── Test 4: Full episode ──────────────────────────────────
    print("\n--- Full episode (25 tasks, random actions) ---")
    env4 = CoToPEnvironment(num_vehicles=1, max_steps=50, seed=42)
    state = env4.reset()
    tasks = env4.generate_episode_tasks(target_tasks=25)

    total_reward = 0
    for task in tasks:
        action = random.randint(0, 6)
        _, reward, done, info = env4.step(action=action,
                                          current_task=task)
        total_reward += reward
        if done:
            break

    metrics = env4.get_metrics()
    print(f"Total reward:     {total_reward:.4f}")
    print(f"Avg delay:        {metrics['avg_delay']:.4f}s")
    print(f"Avg energy:       {metrics['avg_energy']:.4f}J")
    print(f"Completion ratio: {metrics['completion_ratio']:.3f}")
    print(f"Completed:        {metrics['completed']}")
    print(f"Failed:           {metrics['failed']}")
    print(f"Generated:        {metrics['generated']}")