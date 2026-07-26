class Task:
    """
    CoTOP Task Model.

    Each task:
        s_n,i(t) = {rho, phi, d}

    rho  : task input data size (Mbits)
    phi  : required CPU cycles (Mcycles)
    d    : maximum tolerable delay (seconds)

    Based on CoTOP Eq. (3)-(6).
    """

    # ==========================================================
    # Execution cases
    # ==========================================================

    STANDALONE = 0       # Case 1: same RSU completes task
    COLLABORATIVE = 1    # Case 2: multiple RSUs cooperate


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


    def __init__(self, task_id, owner_id, size, cpu_cycles, deadline):

        # ======================================================
        # Identity
        # ======================================================

        self.task_id = task_id
        self.owner_id = owner_id        # vehicle ID


        # ======================================================
        # Paper task model:
        # s_n,i(t) = {rho, phi, d}
        # ======================================================

        self.size = size                # rho: Mbits
        self.cpu_cycles = cpu_cycles    # phi: Mcycles
        self.deadline = deadline        # d: seconds


        # ======================================================
        # Execution decision
        # ======================================================

        self.execution_case = None

        self.assigned_rsu_id = None     # primary RSU
        self.collab_rsu_id = None       # assisting RSU


        # Eq. (23) priority
        self.priority = 0.0


        # Remaining computation workload
        self.remaining_cycles = cpu_cycles



        # ======================================================
        # Timing information
        # ======================================================

        # Vehicle creates task
        self.created_at = None

        # Task arrives at RSU queue after transmission
        self.arrival_time = None

        # Task completion time
        self.completed_at = None


        # Eq. (3)-(10)
        self.upload_delay = 0.0
        self.processing_delay = 0.0
        self.waiting_delay = 0.0
        self.collab_transfer_delay = 0.0

        self.total_delay = 0.0



        # ======================================================
        # Mobility information
        # ======================================================

        # Predicted vehicle staying time in RSU coverage
        self.dwell_time_at_assignment = None



        # ======================================================
        # Energy model
        # Eq. (11)-(12)
        # ======================================================

        self.computation_energy = 0.0
        self.transmission_energy = 0.0
        self.total_energy = 0.0



        # ======================================================
        # Status
        # ======================================================

        self.status = self.STATUS_PENDING



    @property
    def latency(self):
        """
        End-to-end latency.

        Calculated after task completion:

        latency = completed_at - created_at
        """

        if self.created_at is not None and self.completed_at is not None:
            return self.completed_at - self.created_at

        return None



    @property
    def met_deadline(self):
        """
        Three-state deadline evaluation.

        Returns:
            True  : task completed within deadline
            False : task completed but exceeded deadline
            None  : task is still running
        """

        if self.completed_at is None:
            return None

        return self.latency <= self.deadline



    def __repr__(self):

        return (
            f"Task {self.task_id} | "
            f"owner: V{self.owner_id} | "
            f"size: {self.size:.1f}Mb | "
            f"cpu: {self.cpu_cycles:.1f}Mc | "
            f"deadline: {self.deadline:.1f}s | "
            f"priority: {self.priority:.3f} | "
            f"status: {self.status}"
        )



# ==============================================================
# Verification
# ==============================================================

if __name__ == "__main__":

    task1 = Task(
        task_id="v1-0",
        owner_id=1,
        size=5.0,          # 5 Mbits
        cpu_cycles=8.0,    # 8 Mcycles
        deadline=20.0      # 20 seconds
    )


    task2 = Task(
        task_id="v1-1",
        owner_id=1,
        size=2.0,
        cpu_cycles=3.0,
        deadline=10.0
    )


    print("=== Task Model Verification ===")

    print(task1)
    print(task2)

    print()


    # ----------------------------------------------------------
    # Completed task within deadline
    # ----------------------------------------------------------

    task1.created_at = 0.0
    task1.arrival_time = 0.5
    task1.completed_at = 15.0
    task1.status = Task.STATUS_COMPLETED


    print(f"Latency: {task1.latency:.1f}s")
    print(f"Met deadline: {task1.met_deadline}")


    print()


    # ----------------------------------------------------------
    # Completed task exceeding deadline
    # ----------------------------------------------------------

    task2.created_at = 0.0
    task2.arrival_time = 0.5
    task2.completed_at = 12.0
    task2.status = Task.STATUS_COMPLETED


    print(f"T2 latency: {task2.latency:.1f}s")
    print(f"T2 met deadline: {task2.met_deadline}")


    print()


    # ----------------------------------------------------------
    # Running task
    # ----------------------------------------------------------

    task3 = Task(
        task_id="v2-0",
        owner_id=2,
        size=4.0,
        cpu_cycles=6.0,
        deadline=15.0
    )


    print(
        f"Unfinished task met_deadline: {task3.met_deadline}"
    )


    print()

    print("Task cases:")
    print(f"  STANDALONE    = {Task.STANDALONE}")
    print(f"  COLLABORATIVE = {Task.COLLABORATIVE}")