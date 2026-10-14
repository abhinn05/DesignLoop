from lld_practice.domain.problem import (
    DesignConcern,
    Difficulty,
    Problem,
    ProblemCatalog,
    Situation,
    VariationPoint,
)


def build_catalog() -> ProblemCatalog:
    return ProblemCatalog(
        [
            _vending(),
            _parking(),
            _elevator(),
            _booking(),
        ]
    )


def _vending() -> Problem:
    return Problem(
        id="vending-machine",
        title="Vending machine",
        difficulty=Difficulty.INTRO,
        summary="Take money, sell a product, and return change without losing a transaction.",
        statement=(
            "Design a vending machine that sells a small catalog of products. "
            "A person inserts money, selects a product, and either receives the product "
            "and any change due, or gets their money back. The machine must not dispense "
            "a product it cannot complete, and it must not swallow money when a sale fails."
        ),
        requirements=(
            "Track price and remaining stock per product.",
            "Accept money, then a product selection.",
            "Dispense the product and return change when the amount is enough and the item is in stock.",
            "Support cancel, which returns the money inserted so far.",
            "Refuse a selection that is sold out or underpaid, without losing the inserted amount.",
        ),
        constraints=(
            "One customer transaction at a time is enough.",
            "Model coins and notes as denominations. Do not integrate a real payment gateway.",
            "Inventory and cash inside the machine are both finite.",
        ),
        situations=(
            Situation(
                "sold-out",
                "The selected product is sold out.",
                "Name the type that checks stock before a dispense, and what the customer still holds.",
                ("sold out", "out of stock"),
            ),
            Situation(
                "short",
                "The inserted amount is below the price.",
                "Keep the balance on the transaction until the customer adds money or cancels.",
                ("insufficient", "not enough", "balance"),
            ),
            Situation(
                "change",
                "The machine cannot make exact change.",
                "Decide whether the sale is refused before dispense, and which type owns the change drawer.",
                ("exact change", "cannot make change", "change drawer"),
            ),
            Situation(
                "cancel",
                "The customer cancels mid-transaction.",
                "Return every denomination inserted in this transaction, not a running total from an earlier sale.",
                ("cancel", "refund"),
            ),
        ),
        concerns=(
            DesignConcern(
                "state",
                "Transaction state",
                "Model idle, collecting money, and dispensing as states so money cannot be taken twice.",
                ("machine state", "idle", "dispensing"),
            ),
            DesignConcern(
                "inventory",
                "Inventory separate from payment",
                "Put stock on the product or an inventory type, not inside the coin logic.",
                ("inventory", "stock"),
            ),
            DesignConcern(
                "change",
                "Change making",
                "Isolate how change is chosen so a new denomination does not rewrite dispensing.",
                ("make change", "change drawer", "denomination"),
            ),
            DesignConcern(
                "transaction",
                "One transaction's money",
                "Keep the money inserted for this sale distinct from the machine's cash reserve.",
                ("transaction", "inserted"),
            ),
        ),
        variation_points=(
            VariationPoint(
                "change-policy",
                "How change is made",
                "A greedy drawer and a limited-cash drawer should be swappable.",
                ("make change", "denomination"),
            ),
            VariationPoint(
                "pricing",
                "Price of a product",
                "A price change should not require a new machine type.",
                ("price", "pricing"),
            ),
        ),
        hints=(
            "The interesting bug is a sale that fails after money has moved.",
            "Ask which object is allowed to decrement stock.",
        ),
    )


def _parking() -> Problem:
    return Problem(
        id="parking-lot",
        title="Parking lot",
        difficulty=Difficulty.CORE,
        summary="Park different vehicles across floors, then charge for the stay.",
        statement=(
            "Design a parking lot with more than one floor. Spots come in sizes. "
            "A vehicle may only take a compatible spot. Entering produces a ticket. "
            "Leaving computes a fee from how long the vehicle stayed and what kind of vehicle it is. "
            "The lot must be able to say which spots are still free."
        ),
        requirements=(
            "Represent floors and spots of different sizes.",
            "Park a vehicle only in a compatible free spot, and unpark it with its ticket.",
            "Issue a ticket that records when the stay started.",
            "Compute a fee from duration and vehicle kind.",
            "Report how many spots are free, by size or by floor.",
            "Refuse entry when no compatible spot is free.",
        ),
        constraints=(
            "One entrance is enough.",
            "Keep the model in memory. Do not call a payment provider.",
            "Fee rules will change more often than the act of parking.",
        ),
        situations=(
            Situation(
                "full",
                "A vehicle arrives and every compatible spot is taken.",
                "Name the type that refuses entry, and what the caller receives instead of a ticket.",
                ("lot is full", "no available spot"),
            ),
            Situation(
                "unknown",
                "Someone presents a ticket the lot did not issue.",
                "Reject the ticket at lookup time, before any fee is computed.",
                ("unknown ticket",),
            ),
            Situation(
                "fit",
                "The vehicle does not fit the remaining spots.",
                "Compatibility is a decision of its own, not a chain of if statements in the lot.",
                ("does not fit", "spot size"),
            ),
            Situation(
                "race",
                "Two vehicles ask for the last compatible spot.",
                "The assignment of a spot has to check and claim it as one step.",
                ("two vehicles", "claim"),
            ),
        ),
        concerns=(
            DesignConcern(
                "compat",
                "Vehicle and spot compatibility",
                "Keep vehicle kind and spot size as separate ideas that a policy compares.",
                ("vehicle type", "spot size"),
            ),
            DesignConcern(
                "allocate",
                "Spot allocation",
                "Put the choice of which free spot to take behind an allocation policy.",
                ("allocation policy",),
            ),
            DesignConcern(
                "ticket",
                "Record of the stay",
                "A ticket should carry the entry time and be the only key used to leave.",
                ("entry time", "ticket"),
            ),
            DesignConcern(
                "fee",
                "Fee calculation",
                "Keep fee calculation out of the type that assigns spots.",
                ("fee calculation",),
            ),
            DesignConcern(
                "floor",
                "Floors",
                "A floor groups spots. The lot should not store every spot in one flat list only.",
                ("floor",),
            ),
        ),
        variation_points=(
            VariationPoint(
                "allocation",
                "Which spot is chosen",
                "First-fit and nearest-to-entrance should both sit behind the allocation policy.",
                ("allocation policy",),
            ),
            VariationPoint(
                "pricing",
                "How the fee is computed",
                "A new hourly rate should land in fee calculation, not in parking itself.",
                ("fee calculation",),
            ),
        ),
        hints=(
            "Fees change more often than the act of taking a spot.",
            "A ticket is a record of a stay, not a vehicle.",
        ),
    )


def _elevator() -> Problem:
    return Problem(
        id="elevator",
        title="Elevator control",
        difficulty=Difficulty.CORE,
        summary="Move several cars through hall calls and car calls without reversing early.",
        statement=(
            "Design control for a building with multiple elevators and many floors. "
            "People press hall buttons (up or down) and car buttons (a destination floor). "
            "A car that is already moving should keep its direction until it has served the "
            "requests in that direction. Each car shows its floor and direction. Doors open "
            "only when the car is stopped at a floor it intends to serve."
        ),
        requirements=(
            "Represent multiple cars and the floors of the building.",
            "Accept hall calls with a direction and car calls with a destination.",
            "Decide which car takes a new hall call.",
            "A moving car continues in its current direction while requests remain that way.",
            "Open doors only when the car is stopped at a served floor.",
            "Expose each car's current floor and direction.",
        ),
        constraints=(
            "Time can advance in steps. You do not need a real-time clock.",
            "Ignore weight limits and emergency service for this attempt.",
            "Scheduling policy is expected to change; the car's movement rules less so.",
        ),
        situations=(
            Situation(
                "direction",
                "A car is sent a request behind it while it still has stops ahead.",
                "The car should finish the current direction before reversing.",
                ("current direction", "reverse"),
            ),
            Situation(
                "doors",
                "A hall call arrives while the doors are open.",
                "Door state and motion state should not both be 'active' at once.",
                ("doors", "stopped"),
            ),
            Situation(
                "idle",
                "Every car is idle and two hall calls arrive on different floors.",
                "Assignment of a call is separate from the car executing its stops.",
                ("idle", "hall call"),
            ),
            Situation(
                "same-floor",
                "The requested floor is the car's current floor.",
                "Open the doors instead of issuing a move.",
                ("same floor", "already there"),
            ),
        ),
        concerns=(
            DesignConcern(
                "state",
                "Car state",
                "Treat movement and doors as an explicit state, not a pile of booleans.",
                ("state", "direction"),
            ),
            DesignConcern(
                "schedule",
                "Dispatch versus motion",
                "The policy that assigns a hall call should not be the code that steps a car.",
                ("dispatch", "scheduler", "assignment"),
            ),
            DesignConcern(
                "stops",
                "Stops in each direction",
                "Keep the stops ahead of the car distinct from stops that wait until it reverses.",
                ("stops", "direction"),
            ),
            DesignConcern(
                "buttons",
                "Hall calls and car calls",
                "A hall call has a direction. A car call has only a destination.",
                ("hall call", "car call"),
            ),
        ),
        variation_points=(
            VariationPoint(
                "dispatch",
                "Which car takes a hall call",
                "Nearest-car and least-loaded dispatch should be interchangeable.",
                ("dispatch", "scheduler"),
            ),
            VariationPoint(
                "scan",
                "Order of stops",
                "The scan rule (keep direction, then reverse) should be local to the car.",
                ("current direction", "reverse"),
            ),
        ),
        hints=(
            "A car executing stops is a different job from choosing which car is summoned.",
            "Direction is part of the car's state, not just a button label.",
        ),
    )


def _booking() -> Problem:
    return Problem(
        id="movie-booking",
        title="Movie ticket booking",
        difficulty=Difficulty.STRETCH,
        summary="Hold seats for a show, then confirm them once, without double booking.",
        statement=(
            "Design booking for a cinema. A show plays on one screen at a time and has a seat map. "
            "A customer selects seats, which are held briefly while they pay. "
            "If payment succeeds, the seats become booked. If the customer abandons the hold, "
            "or it expires, the seats return to available. Two customers must not both confirm the same seat."
        ),
        requirements=(
            "Represent screens, shows, and seats.",
            "A seat on a show is available, held, or booked.",
            "Holding seats reserves them for one customer for a limited time.",
            "Confirming a hold books those seats and only those seats.",
            "An expired or cancelled hold releases its seats.",
            "A seat cannot be confirmed by two customers.",
        ),
        constraints=(
            "Payment can be a simple success or failure call. No gateway SDK.",
            "One show's seat map is the consistency boundary you care about.",
            "Hold duration is a rule that product will change.",
        ),
        situations=(
            Situation(
                "double",
                "Two customers confirm the same seat.",
                "The transition from held to booked has to belong to one customer.",
                ("double book", "already held", "one customer"),
            ),
            Situation(
                "expire",
                "A hold expires during payment.",
                "Expiry releases seats only if they are still held by that same hold.",
                ("expires", "expiry", "hold timeout"),
            ),
            Situation(
                "partial",
                "The customer selected a seat that was taken while they were choosing.",
                "Hold creation is all-or-nothing for the requested seats.",
                ("all-or-nothing", "all or nothing"),
            ),
            Situation(
                "cancel",
                "The customer cancels before paying.",
                "Cancel and expiry should share the release path.",
                ("cancel", "release"),
            ),
        ),
        concerns=(
            DesignConcern(
                "identity",
                "Show versus screen versus seat",
                "A seat's availability belongs to a show, not to the screen forever.",
                ("show", "seat map"),
            ),
            DesignConcern(
                "hold",
                "Hold lifetime",
                "A hold has an owner and a deadline. Booked seats no longer have a hold.",
                ("hold", "deadline"),
            ),
            DesignConcern(
                "pay",
                "Payment separate from inventory",
                "Payment success is an input. The booking type decides whether the hold is still valid.",
                ("payment", "confirm"),
            ),
            DesignConcern(
                "status",
                "Seat status",
                "Available, held, and booked are explicit. Do not infer them only from a ticket row.",
                ("available", "booked", "held"),
            ),
        ),
        variation_points=(
            VariationPoint(
                "hold-policy",
                "How long a hold lasts",
                "The deadline rule should be replaceable without rewriting seat transitions.",
                ("deadline", "hold timeout"),
            ),
            VariationPoint(
                "payment",
                "What counts as paid",
                "Confirm should depend on a payment result, not on a concrete gateway.",
                ("payment",),
            ),
        ),
        hints=(
            "The hard part is the life of a hold, not the seat diagram.",
            "Expiry must not release a seat that was already booked.",
        ),
    )
