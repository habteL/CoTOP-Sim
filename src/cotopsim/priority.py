import math

class PriorityAlgorithm:
    """
    CoTOP Task Prioritization Algorithm (Eq. 23).
    P_i = alpha * exp(-1/T_stay) + beta * (rho / d)
    alpha + beta = 1
    """

    def __init__(self, alpha=0.3, beta=0.7):
        assert abs(alpha + beta - 1.0) < 1e-6, \
            "alpha + beta must equal 1.0"
        self.alpha = alpha
        self.beta  = beta

    def compute_priority(self, task, t_stay):
        """
        Compute priority score for a single task (Eq. 23).

        Args:
            task:   Task object with size (Mbits) and deadline (s)
            t_stay: Vehicle dwell time remaining in RSU coverage (s)

        Returns:
            float: priority score (higher = processed first)
        """
        t_stay = max(t_stay, 1e-6)   # prevent division by zero

        mobility_term = self.alpha * math.exp(-1.0 / t_stay)
        urgency_term  = self.beta  * (task.size / task.deadline)

        priority = mobility_term + urgency_term
        task.priority = priority
        return priority

    def sort_tasks(self, tasks, t_stay_map):
        """
        Sort tasks by priority (descending — highest first).

        Args:
            tasks:      list of Task objects
            t_stay_map: dict {task_id: dwell_time}

        Returns:
            list of Task objects sorted by priority
        """
        for task in tasks:
            t_stay = t_stay_map.get(task.task_id, 1.0)
            self.compute_priority(task, t_stay)

        return sorted(tasks,
                      key=lambda t: t.priority,
                      reverse=True)

    def __repr__(self):
        return (f"PriorityAlgorithm | "
                f"alpha={self.alpha} | beta={self.beta}")


if __name__ == "__main__":
    import random
    from cotopsim.task import Task

    random.seed(42)
    algo = PriorityAlgorithm(alpha=0.3, beta=0.7)

    print("=== Sprint 7: Priority Algorithm Verification ===")
    print(f"\n{algo}")

    # ── Test 1: Paper example from Q2 ────────────────────────
    print("\n--- Q2 verification ---")
    tA = Task("A", 1, size=40.0, cpu_cycles=5.0, deadline=20.0)
    tB = Task("B", 2, size=10.0, cpu_cycles=5.0, deadline=25.0)

    pA = algo.compute_priority(tA, t_stay=2.0)
    pB = algo.compute_priority(tB, t_stay=8.0)

    print(f"Task A: P={pA:.5f} (expected 1.58195)")
    print(f"Task B: P={pB:.5f} (expected 0.54475)")
    print(f"A > B:  {pA > pB} (expect True)")

    # ── Test 2: Dwell time effect ─────────────────────────────
    print("\n--- Dwell time effect (same task, varying T_stay) ---")
    t_ref = Task("ref", 1, size=20.0,
                 cpu_cycles=5.0, deadline=25.0)
    print(f"{'T_stay':>8} | {'mobility':>10} | "
          f"{'urgency':>10} | {'priority':>10}")
    print("-" * 46)
    for t_stay in [0.5, 1.0, 2.0, 5.0, 10.0, 30.0]:
        mob = 0.3 * math.exp(-1.0 / t_stay)
        urg = 0.7 * (20.0 / 25.0)
        pri = mob + urg
        print(f"{t_stay:>8.1f} | {mob:>10.5f} | "
              f"{urg:>10.5f} | {pri:>10.5f}")

    # ── Test 3: Sort multiple tasks ───────────────────────────
    print("\n--- Multi-task sorting ---")
    tasks = [
        Task("t1", 1, size=40.0, cpu_cycles=8.0, deadline=20.0),
        Task("t2", 1, size=10.0, cpu_cycles=3.0, deadline=30.0),
        Task("t3", 1, size=25.0, cpu_cycles=5.0, deadline=15.0),
        Task("t4", 1, size=5.0,  cpu_cycles=2.0, deadline=25.0),
    ]
    t_stay_map = {
        "t1": 2.0, "t2": 8.0,
        "t3": 3.0, "t4": 10.0
    }
    sorted_tasks = algo.sort_tasks(tasks, t_stay_map)

    print(f"{'Task':>6} | {'size':>6} | {'deadline':>8} | "
          f"{'T_stay':>7} | {'priority':>10}")
    print("-" * 48)
    for t in sorted_tasks:
        print(f"{t.task_id:>6} | {t.size:>6.1f} | "
              f"{t.deadline:>8.1f} | "
              f"{t_stay_map[t.task_id]:>7.1f} | "
              f"{t.priority:>10.5f}")