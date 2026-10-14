"""Hand-written designs used to check that the rubric separates a real sketch from a thin one."""


def strong_parking() -> dict:
    return {
        "assumptions": (
            "I assume one entrance and in-memory state because a durable ledger is out of scope. "
            "Vehicles are classified by vehicle type before they park."
        ),
        "classes": [
            {
                "name": "ParkingLot",
                "responsibility": "Coordinates one stay: admits a vehicle, issues a ticket, and closes the stay on exit.",
                "collaborators": ["SpotAllocator", "TicketDesk", "Pricing"],
            },
            {
                "name": "SpotAllocator",
                "responsibility": "Chooses a free spot for a vehicle type using an allocation policy.",
                "collaborators": ["ParkingSpot"],
            },
            {
                "name": "ParkingSpot",
                "responsibility": "Tracks one spot size and whether that spot is currently free.",
                "collaborators": ["Floor"],
            },
            {
                "name": "Floor",
                "responsibility": "Groups the spots on one floor and reports which of them are free.",
                "collaborators": ["ParkingSpot"],
            },
            {
                "name": "TicketDesk",
                "responsibility": "Issues a ticket that stores the vehicle type and the entry time.",
                "collaborators": ["Ticket"],
            },
            {
                "name": "Pricing",
                "responsibility": "Owns fee calculation from the duration and the vehicle type.",
                "collaborators": ["Ticket"],
            },
        ],
        "relationships": (
            "ParkingLot depends on the SpotAllocator interface and does not expose the spot-search invariant. "
            "Pricing is not called while a spot is being claimed."
        ),
        "tradeoffs": (
            "I used an allocation policy instead of hard-coding first-fit inside ParkingLot because the selection "
            "rule changes more often than admission. The cost is an extra type, and the simpler alternative was "
            "one method on ParkingLot."
        ),
        "extensibility": (
            "A new vehicle type means a new class plus a pricing rule. The ParkingLot stays the same without "
            "changing its admission flow. Only the allocation policy and the fee calculation change."
        ),
        "edge_cases": (
            "If the lot is full there is no available spot and ParkingLot refuses entry. An unknown ticket is "
            "rejected before a fee. A vehicle that does not fit the spot size is not assigned. Two vehicles "
            "asking for the last spot must claim it as one step."
        ),
    }


def weak_parking() -> dict:
    return {
        "assumptions": "A parking lot stores cars.",
        "classes": [
            {
                "name": "Lot",
                "responsibility": "Manages everything and handles all data and rules and users.",
                "collaborators": [],
            },
            {
                "name": "Car",
                "responsibility": "Holds the car number.",
                "collaborators": [],
            },
        ],
        "relationships": "Lot has cars inside it always.",
        "tradeoffs": "Simple is better for now.",
        "extensibility": "Add more features later if needed.",
        "edge_cases": "Handle bad input somehow.",
    }
