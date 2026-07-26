class Task:
    """
    CoTOP Task Model.

    Each task:

        s_n,i(t) = {rho, phi, d}

    rho  : task input data size (Mbits)
    phi  : required CPU cycles (Mcycles)
    d    : maximum tolerable delay (seconds)


    Supports:
        Case 1:
            Standalone RSU execution

        Case 2:
            Collaborative RSU execution
    """

    # ==========================================================
    # Execution cases
    # ==========================================================

    STANDALONE = 0
    COLLABORATIVE = 1



    # ==========================================================
    # Task lifecycle states
    # ==========================================================

    STATUS_PENDING = "pending"

    STATUS_UPLOADING = "uploading"

    STATUS_QUEUED = "queued"

    STATUS_PROCESSING = "processing"

    STATUS_COLLABORATING = "collaborating"

    STATUS_COMPLETED = "completed"

    STATUS_FAILED = "failed"



    def __init__(self,
                 task_id,
                 owner_id,
                 size,
                 cpu_cycles,
                 deadline):


        # ======================================================
        # Identity
        # ======================================================

        self.task_id = task_id

        self.owner_id = owner_id



        # ======================================================
        # Task parameters
        #
        # s_n,i(t) = {rho, phi, d}
        # ======================================================

        self.size = size
        # rho: input data size (Mbits)


        self.cpu_cycles = cpu_cycles
        # phi: computation workload (Mcycles)


        self.deadline = deadline
        # d: maximum delay (seconds)



        # ======================================================
        # Execution decision
        # ======================================================

        self.execution_case = None


        # RSU receiving vehicle upload
        # source RSU m
        self.source_rsu_id = None


        # RSU executing final computation
        # may be source RSU or migrated RSU
        self.assigned_rsu_id = None


        # assisting RSU m'
        self.collab_rsu_id = None



        # ======================================================
        # Priority
        # Eq. (23)
        # ======================================================

        self.priority = 0.0



        # ======================================================
        # Computation state
        # ======================================================

        # Remaining computation workload
        self.remaining_cycles = cpu_cycles


        # Remaining workload after handover
        # Eq. (7)
        self.remaining_cycles_after_handover = 0.0



        # ======================================================
        # Timing information
        # ======================================================

        # Task creation time
        self.created_at = None


        # Arrival time at RSU queue
        self.arrival_time = None


        # Completion timestamp
        self.completed_at = None



        # ======================================================
        # Delay components
        #
        # Eq. (3)-(10)
        # ======================================================

        # Vehicle-to-RSU upload
        self.upload_delay = 0.0


        # Computation delay
        self.processing_delay = 0.0


        # Queue waiting delay
        self.waiting_delay = 0.0


        # RSU-to-RSU transfer delay
        self.collab_transfer_delay = 0.0


        # Total end-to-end delay
        self.total_delay = 0.0



        # ======================================================
        # Mobility information
        # ======================================================

        # Remaining time inside selected RSU coverage
        # used as t1
        self.dwell_time_at_assignment = None


        # Time collaboration decision is triggered
        self.collaboration_trigger_time = None



        # ======================================================
        # Energy model
        #
        # Eq. (11)-(12)
        # ======================================================

        self.computation_energy = 0.0

        self.transmission_energy = 0.0

        self.total_energy = 0.0



        # ======================================================
        # Queue / lifecycle status
        # ======================================================

        self.status = self.STATUS_PENDING



    # ==========================================================
    # Latency
    # ==========================================================

    @property
    def latency(self):
        """
        End-to-end latency.

        latency =
            completed_at - created_at
        """

        if (
            self.created_at is not None
            and
            self.completed_at is not None
        ):

            return (
                self.completed_at -
                self.created_at
            )


        return None



    # ==========================================================
    # Deadline evaluation
    # ==========================================================

    @property
    def met_deadline(self):
        """
        Three-state deadline evaluation.

        Returns:

            True
                completed within deadline

            False
                completed but exceeded deadline

            None
                still running
        """

        if self.completed_at is None:

            return None


        return (
            self.latency <=
            self.deadline
        )



    # ==========================================================
    # Display
    # ==========================================================

    def __repr__(self):

        return (
            f"Task {self.task_id} | "
            f"V{self.owner_id} | "
            f"rho={self.size:.1f}Mb | "
            f"phi={self.cpu_cycles:.1f}Mc | "
            f"d={self.deadline:.1f}s | "
            f"priority={self.priority:.3f} | "
            f"case={self.execution_case} | "
            f"source={self.source_rsu_id} | "
            f"assigned={self.assigned_rsu_id} | "
            f"status={self.status}"
        )



# ==============================================================
# Verification
# ==============================================================

if __name__ == "__main__":


    print("=== Task Model Verification ===")


    # ----------------------------------------------------------
    # Standalone task
    # ----------------------------------------------------------

    task1 = Task(
        task_id="v1-0",
        owner_id=1,
        size=20.0,
        cpu_cycles=10.0,
        deadline=25.0
    )


    print(task1)



    # ----------------------------------------------------------
    # Completed within deadline
    # ----------------------------------------------------------

    task1.created_at = 0.0

    task1.completed_at = 15.0

    task1.status = Task.STATUS_COMPLETED


    print(
        "\nLatency:",
        task1.latency,
        "seconds"
    )


    print(
        "Met deadline:",
        task1.met_deadline
    )



    # ----------------------------------------------------------
    # Deadline violation
    # ----------------------------------------------------------

    task2 = Task(
        task_id="v1-1",
        owner_id=1,
        size=30.0,
        cpu_cycles=20.0,
        deadline=10.0
    )


    task2.created_at = 0.0

    task2.completed_at = 12.0

    task2.status = Task.STATUS_COMPLETED


    print(
        "\nTask 2 latency:",
        task2.latency,
        "seconds"
    )


    print(
        "Task 2 deadline:",
        task2.met_deadline
    )



    # ----------------------------------------------------------
    # Collaborative task
    # ----------------------------------------------------------

    task3 = Task(
        task_id="v2-0",
        owner_id=2,
        size=20.0,
        cpu_cycles=10.0,
        deadline=25.0
    )


    task3.execution_case = Task.COLLABORATIVE

    task3.source_rsu_id = 1

    task3.assigned_rsu_id = 2

    task3.collab_rsu_id = 2


    task3.remaining_cycles_after_handover = 4.0


    print("\nCollaborative task:")

    print(task3)


    print(
        "Remaining cycles after handover:",
        task3.remaining_cycles_after_handover,
        "Mc"
    )



    # ----------------------------------------------------------
    # Running task
    # ----------------------------------------------------------

    task4 = Task(
        task_id="v3-0",
        owner_id=3,
        size=16.0,
        cpu_cycles=5.0,
        deadline=20.0
    )


    print(
        "\nRunning task met_deadline:",
        task4.met_deadline
    )


    print("\nExecution cases:")

    print(
        "STANDALONE =",
        Task.STANDALONE
    )

    print(
        "COLLABORATIVE =",
        Task.COLLABORATIVE
    )