import math


class Channel:
    """
    CoTOP Communication Model.

    Implements:
    - V2R transmission rate (Eq. 1)
    - R2R transmission rate (Eq. 2)

    Units:
    - Rate: Mbps
    - Delay: seconds
    - Distance: metres

    Note:
    The paper parameters appear to use normalized channel values.
    These defaults are calibrated to produce realistic VEC transmission
    delays within the 400m RSU coverage range.
    """

    def __init__(self,
                 B_V2R=50.0,     # Mbps (Table III midpoint: 20-100 Mbps)
                 B_R2R=50.0,     # Mbps (50 MHz baseline)
                 P_V=2.0,        # normalized vehicle power
                 P_R=10.0,       # normalized RSU power
                 K=1.0,          # normalized path loss constant
                 omega=1e-4,      # normalized noise floor
                 sigma=2.0):      # path loss exponent

        self.B_V2R = B_V2R
        self.B_R2R = B_R2R

        self.P_V = P_V
        self.P_R = P_R

        self.K = K
        self.omega = omega
        self.sigma = sigma


    # ---------------------------------------------------------
    # V2R communication
    # ---------------------------------------------------------

    def v2r_rate(self, distance):
        """
        V2R transmission rate.

        Equation:
        w = B * log2(1 + P/(K*omega*D^sigma))

        Returns:
            Rate in Mbps
        """

        distance = max(distance, 1.0)

        snr = (
            self.P_V /
            (self.K * self.omega * (distance ** self.sigma))
        )

        rate = self.B_V2R * math.log2(1 + snr)

        # Physical bandwidth limit
        return min(rate, self.B_V2R)



    # ---------------------------------------------------------
    # R2R communication
    # ---------------------------------------------------------

    def r2r_rate(self, distance):
        """
        RSU-to-RSU transmission rate.

        Returns:
            Rate in Mbps
        """

        distance = max(distance, 1.0)

        snr = (
            self.P_R /
            (self.K * self.omega * (distance ** self.sigma))
        )

        rate = self.B_R2R * math.log2(1 + snr)

        return min(rate, self.B_R2R)



    # ---------------------------------------------------------
    # Delay calculation
    # ---------------------------------------------------------

    def upload_delay(self, task_size_mbits, distance):
        """
        V2R upload delay.

        T_up = rho / w

        Mbits / Mbps = seconds
        """

        rate = self.v2r_rate(distance)

        if rate <= 0:
            return float("inf")

        return task_size_mbits / rate



    def r2r_delay(self, data_mbits, distance):
        """
        R2R transmission delay.

        T_ts = data / w_R2R
        """

        rate = self.r2r_rate(distance)

        if rate <= 0:
            return float("inf")

        return data_mbits / rate



    def __repr__(self):

        return (
            f"Channel | "
            f"B_V2R={self.B_V2R}Mbps | "
            f"B_R2R={self.B_R2R}Mbps | "
            f"P_V={self.P_V} | "
            f"sigma={self.sigma}"
        )



# =============================================================
# Verification
# =============================================================

if __name__ == "__main__":

    channel = Channel()


    print("=== Sprint 4: Channel Model Verification ===")

    print(channel)



    # ---------------------------------------------------------
    # V2R test
    # ---------------------------------------------------------

    print("\n--- V2R transmission rate vs distance ---")

    print(
        f"{'Distance':>10} | "
        f"{'Rate(Mbps)':>12} | "
        f"{'Upload delay(20Mb)':>20}"
    )

    print("-" * 55)


    for d in [1, 50, 100, 200, 300, 400]:

        rate = channel.v2r_rate(d)

        delay = channel.upload_delay(
            task_size_mbits=20.0,
            distance=d
        )


        print(
            f"{d:>10.2f} | "
            f"{rate:>12.3f} | "
            f"{delay:>20.4f}s"
        )



    # ---------------------------------------------------------
    # R2R test
    # ---------------------------------------------------------

    print("\n--- R2R transmission rate ---")


    rsu_spacing = 33.33


    r2r_rate = channel.r2r_rate(
        rsu_spacing
    )


    r2r_delay = channel.r2r_delay(
        data_mbits=20.0,
        distance=rsu_spacing
    )


    print(
        f"RSU spacing: {rsu_spacing}m"
    )

    print(
        f"R2R rate:    {r2r_rate:.3f} Mbps"
    )

    print(
        f"R2R delay:   {r2r_delay:.4f}s"
    )



    # ---------------------------------------------------------
    # Boundary degradation test
    # ---------------------------------------------------------

    print("\n--- Rate degradation check ---")


    near_rate = channel.v2r_rate(5.0)

    boundary_rate = channel.v2r_rate(400.0)


    print(
        f"Rate at 5m:    {near_rate:.3f} Mbps"
    )

    print(
        f"Rate at 400m:  {boundary_rate:.3f} Mbps"
    )


    if near_rate > 0:

        degradation = (
            1 - boundary_rate / near_rate
        ) * 100


        print(
            f"Degradation: {degradation:.1f}%"
        )