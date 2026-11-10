"""
Station Topology, Distance and Fare Logic
------------------------------------------
One circular metro line with 8 stations (0..7), trains run in one direction:
0 -> 1 -> ... -> 7 -> 0.

Fare slabs by forward distance:
  0 stops  -> Rs 0   (same station — only via excess_fare, never via fare())
  1-2 stops -> Rs 10
  3-5 stops -> Rs 20
  6-7 stops -> Rs 30
"""

import config


# 8 placeholder station names for the UI
STATION_NAMES = [
    "Central",
    "Park Street",
    "Lake View",
    "Tech Park",
    "City Mall",
    "Old Town",
    "Airport",
    "University",
]


def distance(src: int, dst: int) -> int:
    """
    Forward distance on the circular line.
    distance(src, dst) = (dst - src) % NUM_STATIONS
    """
    return (dst - src) % config.NUM_STATIONS


def fare_for_distance(d: int) -> int:
    """
    Fare slab lookup by forward distance.
    0 -> 0, 1-2 -> 10, 3-5 -> 20, 6-7 -> 30.
    """
    if d == 0:
        return 0
    elif d <= 2:
        return 10
    elif d <= 5:
        return 20
    else:
        return 30


def fare(src: int, dst: int) -> int:
    """
    Fare from source to destination.
    Raises ValueError if src == dst or either station ID is out of range.
    """
    if src < 0 or src >= config.NUM_STATIONS or dst < 0 or dst >= config.NUM_STATIONS:
        raise ValueError(f"Station ID out of range: src={src}, dst={dst}")
    if src == dst:
        raise ValueError(f"Source and destination are the same: {src}")
    return fare_for_distance(distance(src, dst))


def excess_fare(src: int, exit_station: int, paid_fare: int) -> int:
    """
    Extra amount owed when exiting at exit_station instead of the booked destination.
    Returns max(0, fare_for_distance(distance(src, exit_station)) - paid_fare).
    """
    actual_fare = fare_for_distance(distance(src, exit_station))
    return max(0, actual_fare - paid_fare)


def check_payment(inserted: int, fare_amount: int) -> tuple:
    """
    Checks if the inserted amount covers the fare.
    Returns ("pay_ok", change) if sufficient, else ("pay_fail", 0).
    The symbols "pay_ok" and "pay_fail" are the Booking DFA's symbols.
    """
    if inserted >= fare_amount:
        return ("pay_ok", inserted - fare_amount)
    else:
        return ("pay_fail", 0)
