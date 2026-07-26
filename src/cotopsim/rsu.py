import random
from cotopsim.task import Task


class RSU:
    """
    CoTOP Road-Side Unit (RSU) model.

    Features:
    - M/M/1 computation queue
    - Task processing
    - Waiting delay calculation
    - RSU collaboration structure
    - 400m coverage from Table III
    """


    def __init__(self,
                 rsu_id,
                 x,
                 capacity,
                 coverage_radius,
                 neighbor_ids=None):

        # -----------------------------------------------------
        # Identity and position
        # -----------------------------------------------------

        self.rsu_id = rsu_id
        self.x = x
        self.capacity = capacity              # Mcycles/s
        self.coverage_radius = coverage_radius


        # -----------------------------------------------------
        # Neighbor RSUs
        # -----------------------------------------------------

        self.neighbor_ids = neighbor_ids or []
        self.neighbors = {}                   # {id: RSU}



        # -----------------------------------------------------
        # Computation queue
        # -----------------------------------------------------

        self.task_queue = []
        self.current_task = None

        self.tasks_processed = 0



        # -----------------------------------------------------
        # Completed tasks in current step
        # -----------------------------------------------------

        self.completed_tasks = []



        # -----------------------------------------------------
        # R2R communication cache
        # -----------------------------------------------------

        self.r2r_rates = {}



    # =========================================================
    # Coverage
    # =========================================================

    def in_range(self, vehicle):
        """
        Check whether vehicle is inside RSU coverage.
        """

        distance = abs(self.x - vehicle.x)

        return distance <= self.coverage_radius



    # =========================================================
    # Queue calculation
    # =========================================================

    def queued_cycles(self):
        """
        Total remaining computation cycles.

        N_queue(t)
        =
        waiting tasks + current processing task
        """

        total = sum(
            task.remaining_cycles
            for task in self.task_queue
        )


        if self.current_task is not None:

            total += self.current_task.remaining_cycles


        return total



    def waiting_delay(self):
        """
        Eq. (5):

        T_wait = N_queue / F_RSU

        Unit:
        seconds
        """

        if self.capacity <= 0:

            return float("inf")


        return self.queued_cycles() / self.capacity



    # =========================================================
    # Task management
    # =========================================================

    def accept_task(self, task, arrival_time):
        """
        Accept task into RSU queue.
        """

        task.arrival_time = arrival_time

        task.waiting_delay = self.waiting_delay()

        task.queue_enter_time = arrival_time

        task.assigned_rsu_id = self.rsu_id

        task.status = Task.STATUS_QUEUED


        self.task_queue.append(task)



    # =========================================================
    # Processing
    # =========================================================

    def tick(self, dt=1.0):
        """
        Advance RSU computation.

        Process:
        cycles = capacity × time
        """

        # -----------------------------------------------------
        # Start next task if RSU idle
        # -----------------------------------------------------

        if self.current_task is None:

            if self.task_queue:

                self.current_task = self.task_queue.pop(0)

                self.current_task.status = (
                    Task.STATUS_PROCESSING
                )



        if self.current_task is None:

            return



        # -----------------------------------------------------
        # Execute computation
        # -----------------------------------------------------

        cycles_processed = self.capacity * dt

        self.current_task.remaining_cycles -= cycles_processed



        # -----------------------------------------------------
        # Task completion
        # -----------------------------------------------------

        if self.current_task.remaining_cycles <= 0:


            self.current_task.remaining_cycles = 0


            self.current_task.status = (
                Task.STATUS_COMPLETED
            )


            self.tasks_processed += 1


            self.completed_tasks.append(
                self.current_task
            )


            self.current_task = None



            # Immediately start next task
            if self.task_queue:

                self.current_task = self.task_queue.pop(0)

                self.current_task.status = (
                    Task.STATUS_PROCESSING
                )



    # =========================================================
    # Reset
    # =========================================================

    def reset(self):
        """
        Reset RSU state between episodes.
        """

        self.task_queue = []

        self.current_task = None

        self.tasks_processed = 0

        self.completed_tasks = []

        self.r2r_rates = {}



    # =========================================================
    # Display
    # =========================================================

    def __repr__(self):

        state = (
            "busy"
            if self.current_task
            else "idle"
        )


        return (
            f"RSU {self.rsu_id} | "
            f"x={self.x:.2f}m | "
            f"capacity={self.capacity:.1f}Mc/s | "
            f"coverage={self.coverage_radius}m | "
            f"{state} | "
            f"queue={len(self.task_queue)} | "
            f"neighbors={self.neighbor_ids}"
        )



# =============================================================
# Verification
# =============================================================

if __name__ == "__main__":

    from cotopsim.vehicle import Vehicle


    random.seed(42)



    # ---------------------------------------------------------
    # Table III parameters
    # ---------------------------------------------------------

    ROAD_LENGTH = 200.0

    NUM_RSUS = 6

    COVERAGE_RADIUS = 400.0

    CAPACITY = 2000.0       # midpoint of 1-4 Gcycles/s


    spacing = ROAD_LENGTH / NUM_RSUS



    rsus = {}



    # ---------------------------------------------------------
    # Create RSUs
    # ---------------------------------------------------------

    for i in range(1, NUM_RSUS + 1):

        x = spacing * (i - 0.5)


        neighbors = []


        if i > 1:

            neighbors.append(i - 1)


        if i < NUM_RSUS:

            neighbors.append(i + 1)



        rsus[i] = RSU(
            rsu_id=i,
            x=x,
            capacity=CAPACITY,
            coverage_radius=COVERAGE_RADIUS,
            neighbor_ids=neighbors
        )



    # Link neighbors

    for rsu in rsus.values():

        rsu.neighbors = {
            nid: rsus[nid]
            for nid in rsu.neighbor_ids
        }



    print("=== Sprint 3: Revised RSU Verification ===")



    print("\n--- RSU Configuration ---")

    for rsu in rsus.values():

        print(rsu)



    # ---------------------------------------------------------
    # Waiting delay test
    # ---------------------------------------------------------

    print("\n--- Waiting Delay Test ---")


    rsu3 = rsus[3]


    t1 = Task(
        "t1",
        1,
        size=25.0,
        cpu_cycles=8.0,
        deadline=20.0
    )


    t2 = Task(
        "t2",
        1,
        size=18.0,
        cpu_cycles=5.0,
        deadline=25.0
    )



    rsu3.accept_task(t1, 0.0)

    rsu3.accept_task(t2, 0.0)



    print(
        f"Queued cycles: "
        f"{rsu3.queued_cycles():.2f} Mc"
    )


    print(
        f"Waiting delay: "
        f"{rsu3.waiting_delay():.6f}s"
    )



    # ---------------------------------------------------------
    # Processing test
    # ---------------------------------------------------------

    print("\n--- Processing Test ---")


    rsu_test = rsus[3]

    rsu_test.reset()



    t3 = Task(
        "t3",
        2,
        size=20.0,
        cpu_cycles=2.0,
        deadline=20.0
    )



    rsu_test.accept_task(
        t3,
        arrival_time=0.0
    )



    steps = 0


    while (
        t3.status != Task.STATUS_COMPLETED
        and steps < 100
    ):

        rsu_test.tick(
            dt=0.001
        )

        steps += 1



    print(
        f"Completed after {steps} steps"
    )


    print(
        f"Simulation time: {steps*0.001:.4f}s"
    )


    print(
        f"Status: {t3.status}"
    )



    # ---------------------------------------------------------
    # Coverage test
    # ---------------------------------------------------------

    print("\n--- Coverage Test ---")


    vehicle = Vehicle(
        vehicle_id=1,
        x=80.0,
        speed=35.0
    )



    for rsu in rsus.values():

        print(
            f"RSU {rsu.rsu_id} "
            f"(x={rsu.x:.2f}m): "
            f"in_range={rsu.in_range(vehicle)}"
        )