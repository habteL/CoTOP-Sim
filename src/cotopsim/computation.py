from cotopsim.task import Task


class ComputationModel:
    """
    CoTOP Computation and Energy Model.

    Implements:

    Standalone:
        Eq.(3)  Upload delay
        Eq.(4)  Processing delay
        Eq.(5)  Waiting delay
        Eq.(6)  Total delay

    Collaborative:
        Eq.(7)  Remaining cycles
        Eq.(8)  R2R transmission
        Eq.(9)  Remaining processing
        Eq.(10) Collaborative delay

    Energy:
        Eq.(11) Computation energy
        Eq.(12) Transmission energy

    Units:
        Delay : seconds
        Energy: Joules
        Power : Watts
    """

    def __init__(self,
                 P_RSU=10.0,
                 P_V2R=5.0,
                 P_R2R=8.0):

        self.P_RSU = P_RSU
        self.P_V2R = P_V2R
        self.P_R2R = P_R2R



    # =========================================================
    # Standalone Model
    # =========================================================

    def upload_delay(self, task, vehicle, rsu, channel):

        distance = abs(vehicle.x - rsu.x)

        return channel.upload_delay(
            task.size,
            distance
        )


    def processing_delay(self, task, rsu):

        return task.cpu_cycles / rsu.capacity



    def waiting_delay(self, rsu):

        return rsu.waiting_delay()



    def total_standalone_delay(self,
                               task,
                               vehicle,
                               rsu,
                               channel):

        t_up = self.upload_delay(
            task,
            vehicle,
            rsu,
            channel
        )

        t_pro = self.processing_delay(
            task,
            rsu
        )

        t_wait = self.waiting_delay(
            rsu
        )


        task.upload_delay = t_up
        task.processing_delay = t_pro
        task.waiting_delay = t_wait

        task.total_delay = (
            t_up +
            t_pro +
            t_wait
        )

        task.execution_case = Task.STANDALONE

        return task.total_delay



    # =========================================================
    # Collaborative Model
    # =========================================================

    def remaining_cycles(self,
                         task,
                         t1,
                         rsu):

        """
        Eq.(7)

        phi_rest =
            phi - t1 * F_RSU
        """

        completed = (
            t1 *
            rsu.capacity
        )

        return max(
            0.0,
            task.cpu_cycles - completed
        )



    def needs_collaboration(self,
                            task,
                            t1,
                            rsu):

        """
        Collaboration condition:

        t1 * F_RSU < phi
        """

        return (
            t1 *
            rsu.capacity
            <
            task.cpu_cycles
        )



    def r2r_transfer_delay(self,
                           task,
                           rsu,
                           next_rsu,
                           channel):

        """
        Eq.(8)

        T_ts = rho / w_R2R
        """

        distance = abs(
            rsu.x -
            next_rsu.x
        )

        return channel.r2r_delay(
            task.size,
            distance
        )



    def rest_processing_delay(self,
                              remaining_cycles,
                              rsu):

        """
        Eq.(9)

        T_rest =
            phi_rest / F_RSU
        """

        if remaining_cycles <= 0:
            return 0.0

        return (
            remaining_cycles /
            rsu.capacity
        )



    def collaborative_processing_delay(self,
                                      t1,
                                      t2,
                                      t3):

        """
        Eq.(10)

        Parallel execution:

        max(
            t1,
            t2+t3
        )
        """

        return max(
            t1,
            t2 + t3
        )



    def total_collaborative_delay(self,
                                  task,
                                  vehicle,
                                  rsu,
                                  next_rsu,
                                  channel,
                                  t1):


        remaining = self.remaining_cycles(
            task,
            t1,
            rsu
        )


        t2 = self.r2r_transfer_delay(
            task,
            rsu,
            next_rsu,
            channel
        )


        t3 = self.rest_processing_delay(
            remaining,
            next_rsu
        )


        t_pro = self.collaborative_processing_delay(
            t1,
            t2,
            t3
        )


        t_up = self.upload_delay(
            task,
            vehicle,
            rsu,
            channel
        )


        t_wait = next_rsu.waiting_delay()



        task.upload_delay = t_up
        task.processing_delay = t_pro
        task.waiting_delay = t_wait
        task.collab_transfer_delay = t2


        task.source_rsu_id = rsu.rsu_id
        task.assigned_rsu_id = next_rsu.rsu_id

        task.execution_case = Task.COLLABORATIVE


        task.total_delay = (
            t_up +
            t_pro +
            t_wait
        )


        return task.total_delay



    # =========================================================
    # Energy Model
    # =========================================================


    def total_energy(self, task):

        e_pro = (
            task.processing_delay *
            self.P_RSU
        )


        e_ts = (
            task.upload_delay *
            self.P_V2R
        )


        task.computation_energy = e_pro
        task.transmission_energy = e_ts

        task.total_energy = (
            e_pro +
            e_ts
        )


        return task.total_energy



    def collaborative_energy(self,
                             task,
                             t1,
                             t3):

        """
        Eq.(11)-(12)

        E_pro =
            (t1+t3)*P_RSU

        E_ts =
            T_up*P_V2R +
            T_R2R*P_R2R
        """


        e_pro = (
            (t1 + t3) *
            self.P_RSU
        )


        e_ts = (
            task.upload_delay *
            self.P_V2R
            +
            task.collab_transfer_delay *
            self.P_R2R
        )


        task.computation_energy = e_pro
        task.transmission_energy = e_ts

        task.total_energy = (
            e_pro +
            e_ts
        )


        return task.total_energy



    # =========================================================
    # Unified Evaluation
    # =========================================================


    def evaluate_collaborative(self,
                               task,
                               vehicle,
                               rsu,
                               next_rsu,
                               channel,
                               t1):


        if not self.needs_collaboration(
            task,
            t1,
            rsu
        ):

            delay = self.total_standalone_delay(
                task,
                vehicle,
                rsu,
                channel
            )

            energy = self.total_energy(task)

            return delay, energy, False



        delay = self.total_collaborative_delay(
            task,
            vehicle,
            rsu,
            next_rsu,
            channel,
            t1
        )


        remaining = self.remaining_cycles(
            task,
            t1,
            rsu
        )


        t3 = self.rest_processing_delay(
            remaining,
            next_rsu
        )


        energy = self.collaborative_energy(
            task,
            t1,
            t3
        )


        return delay, energy, True



    def __repr__(self):

        return (
            f"ComputationModel | "
            f"P_RSU={self.P_RSU}W | "
            f"P_V2R={self.P_V2R}W | "
            f"P_R2R={self.P_R2R}W"
        )



# =============================================================
# Verification
# =============================================================

if __name__ == "__main__":

    from cotopsim.vehicle import Vehicle
    from cotopsim.rsu import RSU
    from cotopsim.channel import Channel


    channel = Channel()

    model = ComputationModel()


    print("=== Sprint 6: Collaborative Computation Verification ===")

    print(model)
    print(channel)



    rsu_m = RSU(
        rsu_id=1,
        x=50.0,
        capacity=2000.0,
        coverage_radius=400.0
    )


    rsu_m2 = RSU(
        rsu_id=2,
        x=83.33,
        capacity=2000.0,
        coverage_radius=400.0
    )


    vehicle = Vehicle(
        vehicle_id=5,
        x=50.0,
        speed=35.0
    )



    # ---------------------------------------------------------
    # Collaboration required
    # ---------------------------------------------------------

    print("\n--- Collaboration Required ---")


    task = Task(
        "c1",
        5,
        size=20.0,
        cpu_cycles=10.0,
        deadline=25.0
    )


    t1 = 0.003


    print(
        f"Dwell time: {t1}s"
    )

    print(
        f"Processable cycles: "
        f"{t1*rsu_m.capacity:.4f}"
    )


    print(
        f"Needs collaboration: "
        f"{model.needs_collaboration(task,t1,rsu_m)}"
    )


    remaining = model.remaining_cycles(
        task,
        t1,
        rsu_m
    )


    t2 = model.r2r_transfer_delay(
        task,
        rsu_m,
        rsu_m2,
        channel
    )


    t3 = model.rest_processing_delay(
        remaining,
        rsu_m2
    )


    print(
        f"Remaining cycles: {remaining:.4f} Mc"
    )

    print(
        f"R2R delay: {t2:.4f}s"
    )

    print(
        f"Remaining processing: {t3:.6f}s"
    )



    delay, energy, flag = model.evaluate_collaborative(
        task,
        vehicle,
        rsu_m,
        rsu_m2,
        channel,
        t1
    )


    print(
        f"Total delay: {delay:.4f}s"
    )

    print(
        f"Energy: {energy:.4f}J"
    )

    print(
        f"Collaborated: {flag}"
    )



    # ---------------------------------------------------------
    # No collaboration
    # ---------------------------------------------------------

    print("\n--- Standalone Case ---")


    task2 = Task(
        "c2",
        5,
        size=20.0,
        cpu_cycles=10.0,
        deadline=25.0
    )


    delay2, energy2, flag2 = model.evaluate_collaborative(
        task2,
        vehicle,
        rsu_m,
        rsu_m2,
        channel,
        10.0
    )


    print(
        f"Total delay: {delay2:.4f}s"
    )

    print(
        f"Energy: {energy2:.4f}J"
    )

    print(
        f"Collaborated: {flag2}"
    )