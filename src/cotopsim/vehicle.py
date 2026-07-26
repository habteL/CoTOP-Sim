import random
from cotopsim.task import Task


class Vehicle:
    """
    CoTOP Vehicle model.

    Phase 1:
    - Uni-directional highway mobility
    - Analytical dwell-time estimation
    - Task generation based on Table III parameters
    """

    def __init__(self, vehicle_id, x, speed, direction=1):
        """
        Args:
            vehicle_id: Unique vehicle identifier
            x: Initial position (metres)
            speed: Vehicle speed (m/s), paper uses 30-40 m/s
            direction: +1 forward, -1 reserved for future extension
        """
        self.vehicle_id   = vehicle_id
        self.x            = x
        self.speed        = speed
        self.direction    = direction

        self.task_counter = 0


    def move(self, dt=1.0):
        """
        Update vehicle position.

        x(t+dt) = x(t) + v*dt
        """
        self.x += self.direction * self.speed * dt


    def estimate_dwell_time(self, rsu):
        """
        Estimate remaining time inside RSU coverage.

        Phase 1 analytical substitute for mobility prediction.

        Returns:
            Remaining dwell time in seconds.
            Always >= 0.
        """

        distance = abs(self.x - rsu.x)

        # Vehicle outside RSU coverage
        if distance > rsu.coverage_radius:
            return 0.0

        # Stationary vehicle
        if self.speed == 0:
            return float("inf")


        # Forward highway traffic
        if self.direction == 1:
            exit_boundary = rsu.x + rsu.coverage_radius

        # Backward extension support
        else:
            exit_boundary = rsu.x - rsu.coverage_radius


        remaining_distance = abs(exit_boundary - self.x)

        if remaining_distance <= 0:
            return 0.0


        return remaining_distance / self.speed



    def generate_tasks(
            self,
            current_time,
            num_tasks=None,
            size_range=(16.0, 40.0),
            cpu_range=(1.0, 10.0),
            deadline_range=(20.0, 30.0)):
        """
        Generate computational tasks.

        Table III:
        - Number of tasks: 20-40 total
        - Task size: 2-5 MB = 16-40 Mbits
        - CPU cycles: 1-10 Mcycles
        - Deadline: 20-30 seconds

        Returns:
            List of Task objects
        """

        if num_tasks is None:
            num_tasks = random.randint(1, 3)


        tasks = []

        for _ in range(num_tasks):

            task = Task(
                task_id=f"v{self.vehicle_id}-{self.task_counter}",
                owner_id=self.vehicle_id,
                size=round(random.uniform(*size_range), 2),
                cpu_cycles=round(random.uniform(*cpu_range), 2),
                deadline=round(random.uniform(*deadline_range), 2)
            )

            task.created_at = current_time

            self.task_counter += 1

            tasks.append(task)


        return tasks



    def __repr__(self):

        direction_symbol = "→" if self.direction == 1 else "←"

        return (
            f"Vehicle {self.vehicle_id} | "
            f"x={self.x:.1f}m | "
            f"speed={self.speed:.1f}m/s | "
            f"dir={direction_symbol}"
        )



if __name__ == "__main__":

    random.seed(42)


    # ---------------------------------------------------------
    # RSU stub for testing
    # ---------------------------------------------------------

    class RSUStub:

        def __init__(self, x, radius):
            self.x = x
            self.coverage_radius = radius



    # Paper parameters
    RSU_POSITION = 100.0
    RSU_RADIUS   = 400.0


    rsu = RSUStub(
        x=RSU_POSITION,
        radius=RSU_RADIUS
    )


    print("=== Sprint 2: Revised Vehicle Verification ===")


    # ---------------------------------------------------------
    # Test 1: Dwell time inside coverage
    # ---------------------------------------------------------

    v1 = Vehicle(
        vehicle_id=1,
        x=90.0,
        speed=30.0,
        direction=1
    )


    print("\n--- Vehicle information ---")
    print(v1)

    distance = abs(v1.x - rsu.x)

    print(f"Distance to RSU: {distance:.2f}m")

    dwell = v1.estimate_dwell_time(rsu)

    print(f"Dwell time: {dwell:.2f}s")

    expected = (RSU_POSITION + RSU_RADIUS - v1.x) / v1.speed

    print(f"Expected: {expected:.2f}s")



    # ---------------------------------------------------------
    # Test 2: Mobility update
    # ---------------------------------------------------------

    print("\n--- Mobility test ---")

    for step in range(3):

        v1.move(dt=1.0)

        print(
            f"Step {step+1}: "
            f"x={v1.x:.1f}m | "
            f"dwell={v1.estimate_dwell_time(rsu):.2f}s"
        )



    # ---------------------------------------------------------
    # Test 3: Outside coverage
    # ---------------------------------------------------------

    print("\n--- Outside coverage test ---")


    v2 = Vehicle(
        vehicle_id=2,
        x=-500.0,
        speed=35.0
    )


    print(v2)

    print(
        f"Dwell time: "
        f"{v2.estimate_dwell_time(rsu):.2f}s "
        "(expected 0.0)"
    )



    # ---------------------------------------------------------
    # Test 4: Task generation
    # ---------------------------------------------------------

    print("\n--- Task generation test ---")


    v3 = Vehicle(
        vehicle_id=3,
        x=150.0,
        speed=35.0
    )


    tasks = v3.generate_tasks(
        current_time=0.0
    )


    print(f"Generated {len(tasks)} tasks:")

    for task in tasks:
        print(task)