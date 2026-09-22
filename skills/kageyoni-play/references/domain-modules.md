# Play module routing

Load only modules whose trigger is present. All modules share one action resolution, one request ID, one optional roll ID, one declared time operation, and one cost/effect ledger.

| Module | Use when | Read | May declare | Does not decide |
| --- | --- | --- | --- | --- |
| `kageyoni.combat` | contested harm, defense, positioning, surrender, or escape | participants, capabilities, injuries, equipment, environment, visibility | permission/probability/magnitude/cost inputs | a character's motive, automatic defeat, or universal combat rules |
| `kageyoni.travel` | movement, route choice, navigation, exposure, water, weather, or deadline | locations, routes, positions, hazards, clock, fatigue, political access | route feasibility, timing, exposure, route consequences | unit conversion or safe passage when canon is silent |
| `kageyoni.discovery` | search, investigation, observation, recognition, or hidden fact | authorized context, knowledge, source records, environment | observation, belief update, or discovery consequence | leaking hidden facts or treating belief as truth |
| `kageyoni.training` | practice, learning, repair, demonstrated capability, or recovery | capability, progression, fatigue, injury, cost, time | bounded progression and a possible background process | unexplained mastery tiers or automatic freedom growth |
| `kageyoni.social` | negotiation, trust, obligation, refusal, collective response, or politics | directional relationships, roles, knowledge, claims, offices, factions | relationship or political changes and individual choices | erasing dissent, coercing agreement, or an agency score |
| `kageyoni.downtime` | rest, waiting, repair, recovery, or quiet work | injuries, fatigue, resources, process state, clock | explicit interval and supported elapsed-time effects | passive checks every moment or automatic healing |

Mixed routing example: a family crossing a damaged bridge with changing water can use travel, discovery, social, and downtime inputs in one action. The engine should receive one command with each module as a declared dependency; the GM supplies any unresolved judgment once.
