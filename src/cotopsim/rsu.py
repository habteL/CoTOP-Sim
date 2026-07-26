import math
from cotopsim.task import Task

class RSU:
    """
    CoTOP Road-Side Unit (RSU) model.
    Models an M/M/1 queue with collaborative offloading support.
    """

    def __init__(self, rsu_id, x, capacity, coverage_radius,
                 neighbor_ids=None):
        # ── Identity and position ─────────────────────────────
        self.rsu_id          = rsu_id
        self.x               = x                 # metres
        self.capacity        = capacity           # F_m, Mcycles/second
        self.coverage_radius = coverage_radius    # metres

        # ── Neighbor RSUs for collaboration ───────────────────
        self.neighbor_ids    = neighbor_ids or [] # adjacent RSU IDs
        self.neighbors       = {}  # filled in by environment: {id: RSU}

        # ── Task queue (M/M/1) ────────────────────────────────
        self.task_queue      = []   # waiting tasks
        self.current_task    = None # task being processed
        self.tasks_processed = 0

        # ── Per-step event buffers ────────────────────────────
        self.completed_tasks = []   # cleared each step

        # ── R2R transmission rates (computed once at setup) ───
        self.r2r_rates       = {}   # {neighbor_id: rate Mbps}

    # ── Coverage ─────────────────────────────────────────────
    def in_range(self, vehicle):
        """True if vehicle is within wireless coverage."""
        return abs(self.x - vehicle.x) <= self.coverage_radius

    # ── Queue metrics ─────────────────────────────────────────
    def queued_cycles(self):
        """
        N_m^queue(t) — total CPU cycles of tasks waiting in queue.
        Used in waiting delay calculation (Eq. 5).
        """
        total = sum(t.remaining_cycles for t in self.task_queue)
        if self.current_task is not None:
            total += self.current_task.remaining_cycles
        return total

    def waiting_delay(self):
        """
        T_m,i^wait(t) = N_m^queue(t) / F_m^RSU  (Eq. 5)
        Returns waiting delay in seconds for next arriving task.
        """
        return self.queued_cycles() / self.capacity

    # ── Task acceptance ───────────────────────────────────────
    def accept_task(self, task, arrival_time):
        """Accept a task into the processing queue."""
        task.arrival_time    = arrival_time
        task.waiting_delay   = self.waiting_delay()
        task.assigned_rsu_id = self.rsu_id
        task.status          = Task.STATUS_QUEUED
        self.task_queue.append(task)

    # ── Processing tick ───────────────────────────────────────
    def tick(self, dt=1.0):
        """
        Advance RSU computation by dt seconds.
        Processes current task; pulls next from queue when idle.
        """
        # Pull from queue if idle
        if self.current_task is None and self.task_queue:
            self.current_task        = self.task_queue.pop(0)
            self.current_task.status = Task.STATUS_PROCESSING

        if self.current_task is None:
            return

        # Process cycles
        cycles_done = self.capacity * dt
        self.current_task.remaining_cycles -= cycles_done

        # Task complete
        if self.current_task.remaining_cycles <= 0:
            self.current_task.remaining_cycles = 0
            self.current_task.status           = Task.STATUS_COMPLETED
            self.tasks_processed              += 1
            self.completed_tasks.append(self.current_task)
            self.current_task = None

            # Pull next task immediately
            if self.task_queue:
                self.current_task        = self.task_queue.pop(0)
                self.current_task.status = Task.STATUS_PROCESSING

    # ── Reset ────────────────────────────────────────────────
    def reset(self):
        """Reset all state between episodes."""
        self.task_queue      = []
        self.current_task    = None
        self.tasks_processed = 0
        self.completed_tasks = []

    def __repr__(self):
        busy = "busy" if self.current_task else "idle"
        return (f"RSU {self.rsu_id} | x={self.x:.1f}m | "
                f"capacity={self.capacity}Mc/s | "
                f"status={busy} | "
                f"queue={len(self.task_queue)} tasks | "
                f"queued_cycles={self.queued_cycles():.1f}Mc | "
                f"neighbors={self.neighbor_ids}")


if __name__ == "__main__":
    import random
    from cotopsim.vehicle import Vehicle
    random.seed(42)

    # ── Build 6 RSUs ─────────────────────────────────────────
    ROAD_LENGTH     = 200.0
    NUM_RSUS        = 6
    COVERAGE_RADIUS = 16.67
    CAPACITY        = 1000.0  # Mcycles/second (1 GHz)
    spacing         = ROAD_LENGTH / NUM_RSUS

    rsus = {}
    for i in range(1, NUM_RSUS + 1):
        x           = spacing * (i - 0.5)
        neighbor_ids = []
        if i > 1:
            neighbor_ids.append(i - 1)
        if i < NUM_RSUS:
            neighbor_ids.append(i + 1)
        rsus[i] = RSU(
            rsu_id          = i,
            x               = x,
            capacity        = CAPACITY,
            coverage_radius = COVERAGE_RADIUS,
            neighbor_ids    = neighbor_ids
        )

    # Link neighbor objects
    for rsu in rsus.values():
        rsu.neighbors = {nid: rsus[nid] for nid in rsu.neighbor_ids}

    print("=== Sprint 3: RSU Class Verification ===")
    print("\n--- RSU Configuration ---")
    for rsu in rsus.values():
        print(f"  {rsu}")

    # ── Test waiting delay ────────────────────────────────────
    print("\n--- Waiting delay test ---")
    rsu3 = rsus[3]
    print(f"RSU 3 empty queue waiting delay: {rsu3.waiting_delay():.3f}s")

    # Manually add tasks to queue
    t1 = Task("t1", 1, size=5.0, cpu_cycles=8.0, deadline=20.0)
    t2 = Task("t2", 1, size=3.0, cpu_cycles=5.0, deadline=15.0)
    rsu3.accept_task(t1, arrival_time=0.0)
    rsu3.accept_task(t2, arrival_time=0.0)
    print(f"After 2 tasks (8+5=13 Mc queued):")
    print(f"  queued_cycles = {rsu3.queued_cycles():.1f}Mc")
    print(f"  waiting_delay = {rsu3.waiting_delay():.4f}s")
    print(f"  expected      = {13.0/CAPACITY:.4f}s")

    # ── Test tick processing ──────────────────────────────────
    print("\n--- Tick processing test (dt=0.001s) ---")
    rsu3_test = rsus[3]
    rsu3_test.reset()
    t3 = Task("t3", 2, size=2.0, cpu_cycles=2.0, deadline=10.0)
    rsu3_test.accept_task(t3, arrival_time=0.0)
    print(f"Task accepted: {t3.status}")

    steps = 0
    while t3.status != Task.STATUS_COMPLETED and steps < 100:
        rsu3_test.tick(dt=0.001) #dt=0.001s
        steps += 1

    print(f"Task completed after {steps} steps of dt=0.001s")
    print(f"Total time: {steps * 0.001:.3f}s")
    print(f"Expected:   {2.0/CAPACITY:.3f}s")
    print(f"Status: {t3.status}")

    # ── Test coverage ─────────────────────────────────────────
    print("\n--- Coverage test ---")
    v = Vehicle(vehicle_id=1, x=80.0, speed=10.0)
    for rsu in rsus.values():
        print(f"  RSU {rsu.rsu_id} (x={rsu.x:.1f}): "
              f"in_range={rsu.in_range(v)}")