import math
import random
from cotopsim.task import Task

class Vehicle:
    def __init__(self, vehicle_id, x, speed, direction=1):
        # direction: +1 only in Phase 1 (uni-directional traffic)
        # -1 reserved for Phase 2 bi-directional extension
        self.vehicle_id   = vehicle_id
        self.x            = x          # position on road (metres)
        self.speed        = speed      # m/s
        self.direction    = direction  # +1 = forward
        self.task_counter = 0

    def move(self, dt=1.0):
        """Advance position by one time slot of duration dt seconds."""
        self.x += self.direction * self.speed * dt

    def estimate_dwell_time(self, rsu):
        """
        Analytical dwell time estimation (Phase 1 substitute for GAT).
        Returns time remaining inside RSU coverage, >= 0.
        Assumes uni-directional traffic (direction = +1).
        """
        dist = abs(self.x - rsu.x)

        # Outside coverage
        if dist > rsu.coverage_radius:
            return 0.0

        if self.speed == 0:
            return float('inf')

        # Vehicle moving forward — time until it exits right boundary
        boundary  = rsu.x + rsu.coverage_radius
        remaining = boundary - self.x

        if remaining <= 0:
            return 0.0

        return remaining / self.speed

    def generate_tasks(self, current_time,
                       num_tasks=None,
                       size_range=(1.0, 10.0),
                       cpu_range=(1.0, 10.0),
                       deadline_range=(10.0, 30.0)):
        """
        Generate I tasks per time slot.
        Returns list of Task objects.
        """
        if num_tasks is None:
            num_tasks = random.randint(1, 3)

        tasks = []
        for _ in range(num_tasks):
            task = Task(
                task_id    = f"v{self.vehicle_id}-{self.task_counter}",
                owner_id   = self.vehicle_id,
                size       = round(random.uniform(*size_range), 2),
                cpu_cycles = round(random.uniform(*cpu_range), 2),
                deadline   = round(random.uniform(*deadline_range), 2),
            )
            task.created_at = current_time
            self.task_counter += 1
            tasks.append(task)
        return tasks

    def __repr__(self):
        return (f"Vehicle {self.vehicle_id} | "
                f"x={self.x:.1f}m | "
                f"speed={self.speed:.1f}m/s | "
                f"dir={'→' if self.direction == 1 else '←'}")


if __name__ == "__main__":
    random.seed(42)

    # ── Create a simple RSU stub for testing ──────────────────
    class RSUStub:
        def __init__(self, x, r):
            self.x = x
            self.coverage_radius = r

    rsu = RSUStub(x=100.0, r=16.67)

    # ── Test 1: Vehicle inside coverage, moving forward ───────
    v1 = Vehicle(vehicle_id=1, x=90.0, speed=10.0, direction=1)
    print("=== Sprint 2: Vehicle Class Verification ===")
    print(f"\n{v1}")
    print(f"Distance to RSU centre: {abs(v1.x - rsu.x):.1f}m")
    print(f"Dwell time estimate:    {v1.estimate_dwell_time(rsu):.2f}s")

    # ── Test 2: Move 3 steps ──────────────────────────────────
    print("\n--- Mobility test (3 steps, dt=1s) ---")
    for step in range(3):
        v1.move(dt=1.0)
        dwell = v1.estimate_dwell_time(rsu)
        print(f"Step {step+1}: x={v1.x:.1f}m | dwell={dwell:.2f}s")

    # ── Test 3: Vehicle outside coverage ─────────────────────
    v2 = Vehicle(vehicle_id=2, x=50.0, speed=15.0, direction=1)
    print(f"\nVehicle outside coverage: x={v2.x}m")
    print(f"Dwell time: {v2.estimate_dwell_time(rsu):.2f}s (expect 0.0)")

    
    # ── Test 4: Task generation ───────────────────────────────
    print("\n--- Task generation test ---")
    v4 = Vehicle(vehicle_id=4, x=85.0, speed=12.0, direction=1)
    tasks = v4.generate_tasks(current_time=0.0)
    print(f"Generated {len(tasks)} tasks:")
    for t in tasks:
        print(f"  {t}")