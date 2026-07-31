import numpy as np
import random
import math
from cotopsim.task        import Task
from cotopsim.vehicle     import Vehicle
from cotopsim.rsu         import RSU
from cotopsim.channel     import Channel
from cotopsim.computation import ComputationModel
from cotopsim.priority    import PriorityAlgorithm

class CoToPEnvironmentV2:
    """
    Time-driven CoTOP environment.
    One step = one time slot (1 second).
    Tasks generated probabilistically, complete via RSU simulation.
    """

    NUM_RSUS        = 6
    ROAD_LENGTH     = 200.0
    COVERAGE_RADIUS = 400.0
    RSU_CAPACITY    = 1000.0   # Mcycles/s (1 GHz minimum)
    STATE_DIM       = 21
    ACTION_DIM      = 7
    PENALTY_Z       = 10.0

    NORM_X          = 200.0
    NORM_SPEED      = 40.0
    NORM_SIZE       = 40.0
    NORM_CPU        = 10.0
    NORM_DEADLINE   = 30.0
    NORM_PRIORITY   = 3.0
    NORM_QUEUE      = 100.0    # higher — more tasks queued

    def __init__(self,
                 num_vehicles  = 10,
                 arrival_rate  = 1.5,   # tasks/slot (Poisson)
                 max_slots     = 100,   # episode length
                 target_tasks  = 25,    # stop generating after this
                 sigma         = 0.3,
                 seed          = 42):

        self.num_vehicles  = num_vehicles
        self.arrival_rate  = arrival_rate
        self.max_slots     = max_slots
        self.target_tasks  = target_tasks
        self.sigma         = sigma
        self.seed          = seed

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
        for rsu in self.rsus.values():
            rsu.neighbors = {nid: self.rsus[nid]
                             for nid in rsu.neighbor_ids}

        self.channel    = Channel()
        self.comp_model = ComputationModel()
        self.priority   = PriorityAlgorithm(alpha=0.3, beta=0.7)

        # Episode state
        self.vehicles          = []
        self.current_slot      = 0
        self.all_tasks         = []
        self.total_generated   = 0
        self.pending_exp       = {}   # task_id → experience dict
        self.episode_rewards   = []
        self.episode_metrics   = {
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
        random.seed(self.seed)
        np.random.seed(self.seed)

        for rsu in self.rsus.values():
            rsu.reset()

        self.vehicles        = [self._make_vehicle(i+1)
                                for i in range(self.num_vehicles)]
        self.current_slot    = 0
        self.all_tasks       = []
        self.total_generated = 0
        self.pending_exp     = {}
        self.episode_rewards = []
        self.episode_metrics = {
            'total_delay' : 0.0,
            'total_energy': 0.0,
            'completed'   : 0,
            'failed'      : 0,
            'generated'   : 0
        }
        return []   # no tasks yet — agent acts on each new task

    def _get_task_state(self, task, vehicle):
        """Build 21-element state for a specific task-vehicle pair."""
        serving_rsu = self._find_serving_rsu(vehicle)
        t_stay = vehicle.estimate_dwell_time(serving_rsu) \
            if serving_rsu else 0.0

        sv = [
            vehicle.x     / self.NORM_X,
            vehicle.speed / self.NORM_SPEED,
            min(t_stay, 30.0) / 30.0
        ]

        s_task = [
            task.size       / self.NORM_SIZE,
            task.cpu_cycles / self.NORM_CPU,
            task.deadline   / self.NORM_DEADLINE,
            task.priority   / self.NORM_PRIORITY
        ]
        # Pad to 3 tasks worth of features
        s_task = s_task + [0.0] * 8   # 4 + 8 = 12

        s_rsu = [
            rsu.queued_cycles() / self.NORM_QUEUE
            for rsu in self.rsus.values()
        ]

        state = sv + s_task + s_rsu
        assert len(state) == self.STATE_DIM
        return np.array(state, dtype=np.float32)

    def _find_serving_rsu(self, vehicle):
        candidates = [r for r in self.rsus.values()
                      if r.in_range(vehicle)]
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.queued_cycles())

    def _route_task(self, task, action, vehicle):
        """Route task to RSU based on action."""
        serving_rsu = self._find_serving_rsu(vehicle)
        if serving_rsu is None:
            task.status = Task.STATUS_FAILED
            self.episode_metrics['failed'] += 1
            return None, -self.PENALTY_Z

        if action == 0:
            rsu_target = serving_rsu
        else:
            rsu_target = self.rsus.get(action, serving_rsu)

        # Compute upload delay — task enters queue after upload
        distance = abs(vehicle.x - rsu_target.x)
        upload_delay = self.comp_model.upload_delay(
            task, vehicle, rsu_target, self.channel)

        task.upload_delay    = upload_delay
        task.assigned_rsu_id = rsu_target.rsu_id
        task.source_rsu_id   = serving_rsu.rsu_id

        # Add to RSU queue
        rsu_target.accept_task(task, arrival_time=self.current_slot)

        return rsu_target, None  # reward comes at completion

    def step_slot(self, agent):
        """
        Advance one time slot.
        Returns list of (state, action, reward) for completed tasks.
        """
        self.current_slot += 1
        experiences = []

        # ── 1. Generate new tasks (Poisson arrival) ───────────
        if self.total_generated < self.target_tasks:
            num_new = np.random.poisson(self.arrival_rate)
            num_new = min(num_new,
                          self.target_tasks - self.total_generated)

            for _ in range(num_new):
                # Pick random vehicle
                v = random.choice(self.vehicles)
                new_tasks = v.generate_tasks(
                    current_time=self.current_slot,
                    num_tasks=1,
                    cycles_per_bit=getattr(self, '_cpb', 10.0)
                )
                for task in new_tasks:
                    # Compute priority
                    serving = self._find_serving_rsu(v)
                    t_stay  = v.estimate_dwell_time(serving) \
                        if serving else 1.0
                    self.priority.compute_priority(task, t_stay)

                    # Agent decides routing
                    state  = self._get_task_state(task, v)
                    mask   = self._build_mask(serving)
                    action, _ = agent.select_action(state, mask)

                    # Route task
                    rsu_target, fail_reward = self._route_task(
                        task, action, v)

                    if fail_reward is not None:
                        experiences.append((state, action,
                                            fail_reward))
                    else:
                        # Store pending experience
                        self.pending_exp[task.task_id] = {
                            'state'     : state,
                            'action'    : action,
                            'slot'      : self.current_slot,
                            'vehicle_id': v.vehicle_id
                        }

                    self.all_tasks.append(task)
                    self.total_generated += 1
                    self.episode_metrics['generated'] += 1

        # ── 2. Tick all RSUs ──────────────────────────────────
        for rsu in self.rsus.values():
            rsu.tick(dt=1.0)

        # ── 3. Collect completions ────────────────────────────
        for rsu in self.rsus.values():
            for task in rsu.completed_tasks:
                # latency = (self.current_slot
                #            - task.arrival_time
                #            + task.upload_delay)
                latency = (task.upload_delay +
                            task.waiting_delay +
                            task.processing_delay)
                energy  = self.comp_model.total_energy(task)

                # Compute reward
                if latency > task.deadline:
                    reward = -self.PENALTY_Z
                    task.status = Task.STATUS_FAILED
                    self.episode_metrics['failed'] += 1
                else:
                    reward = -(self.sigma * latency
                               + (1 - self.sigma) * energy)
                    task.status = Task.STATUS_COMPLETED
                    task.total_delay = latency
                    self.episode_metrics['completed'] += 1
                    self.episode_metrics['total_delay']  += latency
                    self.episode_metrics['total_energy'] += energy

                # Retrieve stored experience
                if task.task_id in self.pending_exp:
                    exp = self.pending_exp.pop(task.task_id)
                    experiences.append((
                        exp['state'], exp['action'], reward))

            rsu.completed_tasks.clear()

        # ── 4. Move all vehicles ──────────────────────────────
        for v in self.vehicles:
            v.move(dt=1.0)

        # ── 5. Check termination ──────────────────────────────
        done = self._is_done()
        return experiences, done

    def _build_mask(self, serving_rsu):
        import torch
        mask = torch.ones(self.ACTION_DIM)
        if serving_rsu:
            mask[serving_rsu.rsu_id] = 0
        return mask

    def _is_done(self):
        generation_done = (self.total_generated >= self.target_tasks)
        queues_empty    = all(
            len(r.task_queue) == 0 and r.current_task is None
            for r in self.rsus.values()
        )
        return (generation_done and queues_empty) or \
               self.current_slot >= self.max_slots

    def get_metrics(self):
        m = self.episode_metrics
        n = max(m['completed'], 1)
        return {
            'avg_delay'       : m['total_delay']  / n,
            'avg_energy'      : m['total_energy'] / n,
            'completion_ratio': m['completed'] /
                                max(m['generated'], 1),
            'completed'       : m['completed'],
            'failed'          : m['failed'],
            'generated'       : m['generated'],
            'slots_used'      : self.current_slot
        }

    def __repr__(self):
        return (f"CoToPEnvironmentV2 | "
                f"vehicles={self.num_vehicles} | "
                f"arrival_rate={self.arrival_rate} | "
                f"slot={self.current_slot}/{self.max_slots}")

if __name__ == "__main__":
    import torch
    from cotopsim.agent import A3CAgent

    random.seed(42)
    np.random.seed(42)

    print("=== CoToPEnvironmentV2 Verification ===")

    env   = CoToPEnvironmentV2(
        num_vehicles = 10,
        arrival_rate = 1.5,
        max_slots    = 100,
        target_tasks = 25,
        seed         = 42
    )
    agent = A3CAgent(state_dim=21, action_dim=7)

    print(f"\n{env}")
    env.reset()

    slot = 0
    all_experiences = []

    while True:
        experiences, done = env.step_slot(agent)
        all_experiences.extend(experiences)
        slot += 1

        if slot % 10 == 0 or done:
            m = env.get_metrics()
            print(f"Slot {slot:3d} | "
                  f"generated={env.total_generated} | "
                  f"completed={m['completed']} | "
                  f"failed={m['failed']} | "
                  f"avg_delay={m['avg_delay']:.3f}s | "
                  f"queues={sum(len(r.task_queue) for r in env.rsus.values())}")

        if done:
            break

    print(f"\n=== Episode Complete ===")
    m = env.get_metrics()
    print(f"Slots used:       {m['slots_used']}")
    print(f"Generated:        {m['generated']}")
    print(f"Completed:        {m['completed']}")
    print(f"Failed:           {m['failed']}")
    print(f"Avg delay:        {m['avg_delay']:.3f}s")
    print(f"Avg energy:       {m['avg_energy']:.3f}J")
    print(f"Completion ratio: {m['completion_ratio']:.3f}")
    print(f"Experiences:      {len(all_experiences)}")
    
    print("=== cycles_per_bit Diagnostic (cpb=100) ===")

    cpb = 100

    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    env = CoToPEnvironmentV2(
        num_vehicles=10,
        arrival_rate=1.5,
        max_slots=200,
        target_tasks=25,
        seed=42
    )

    env._cpb = cpb

    agent = A3CAgent(
        state_dim=21,
        action_dim=7
    )

    env.reset()

    while True:
        experiences, done = env.step_slot(agent)
        if done:
            break

    m = env.get_metrics()

    completed = sum(
        1 for t in env.all_tasks
        if t.status == Task.STATUS_COMPLETED
    )

    failed_deadline = sum(
        1 for t in env.all_tasks
        if t.status == Task.STATUS_FAILED
    )

    pending = sum(
        1 for t in env.all_tasks
        if t.status in [
            Task.STATUS_PENDING,
            Task.STATUS_QUEUED,
            Task.STATUS_PROCESSING
        ]
    )

    deadline_exceeded = sum(
        1 for t in env.all_tasks
        if t.status == Task.STATUS_COMPLETED
        and t.total_delay > t.deadline
    )

    print(f"cpb={cpb}")
    print(f"avg_delay={m['avg_delay']:.3f}s")
    print(f"completion_ratio={m['completion_ratio']:.3f}")
    print(f"slots_used={m['slots_used']}")
    print("-----------------------------")
    print(f"generated={len(env.all_tasks)}")
    print(f"completed={completed}")
    print(f"failed_deadline={failed_deadline}")
    print(f"pending={pending}")
    print(f"deadline_exceeded={deadline_exceeded}")