# Co-op Puzzle MVP

## Goal

Add a cooperative puzzle mode inside Dino Memo where:

- two authenticated users join the same room
- both control a character in real time
- they must work together to solve a puzzle
- solving the puzzle moves the room to the next level

This mode is separate from chat and conversation analysis. Dino Memo acts as the hub.

## Product shape

Inside Dino Memo:

- `Chat`
- `Guess Who Said It`
- `Multiplayer`
- `Co-op Puzzle`

The `Co-op Puzzle` tab should:

- let a user create or join a room
- show room code and connection status
- embed the game client
- show basic room state such as player count and current level

## Architecture

### 1. Streamlit hub

Responsibilities:

- authenticated entry point
- create/join room UI
- embed the game client
- pass the PartyKit host and player display name

### 2. Co-op game client

Recommended stack:

- Phaser
- Matter.js physics through Phaser

Responsibilities:

- render map, players, doors, buttons, crates, exit zone
- capture keyboard input
- send movement and interaction messages
- render server-authoritative state

### 3. PartyKit room server

Responsibilities:

- hold canonical room state
- track both players
- validate puzzle progress
- advance level
- broadcast state updates

### 4. Supabase

Responsibilities:

- user authentication
- optional persistence for:
  - room history
  - level progress
  - last completed stage

MVP does not require database persistence for every live physics frame.

## MVP scope

### Players

- exactly 2 players per room
- each player has:
  - `id`
  - `name`
  - `connected`
  - `x`
  - `y`
  - `color`
  - `ready`

### Shared mechanics

- move
- push crate
- stand on pressure plate
- hold switch
- open door
- reach exit

### Not in MVP

- combat
- inventory
- cutting/snipping mechanics
- voice chat
- mobile controls
- matchmaking

## Level design

### Level 1: Twin Switch

Goal:

- both players stand on separate floor switches
- main door opens
- both players enter exit zone

Teaches:

- simultaneous cooperation

### Level 2: Box Relay

Goal:

- one player holds a plate
- the other pushes a crate onto a second plate
- side gate opens
- both players exit

Teaches:

- staggered cooperation
- object interaction

### Level 3: Split Paths

Goal:

- players take different routes
- one activates a remote door for the other
- both regroup at the exit

Teaches:

- timing
- asymmetric roles

### Level 4: Power Core

Goal:

- both players move a heavy core object into a socket
- final door opens

Teaches:

- shared objective and coordinated movement

## Room flow

1. User A opens `Co-op Puzzle`
2. User A creates room `ABCD`
3. User B joins room `ABCD`
4. PartyKit marks room ready when 2 players are present
5. Game starts at level 1
6. Server advances levels when completion conditions are met

## Server-authoritative state

```text
room
  roomId
  phase
  levelIndex
  players
  entities
  puzzleState
  completion
```

Suggested shape:

```json
{
  "roomId": "abcd",
  "phase": "playing",
  "levelIndex": 0,
  "players": {
    "p1": { "id": "p1", "name": "Carlos", "x": 2, "y": 5, "ready": true },
    "p2": { "id": "p2", "name": "Nadine", "x": 8, "y": 5, "ready": true }
  },
  "entities": {
    "crate_1": { "type": "crate", "x": 6, "y": 4 }
  },
  "puzzleState": {
    "switch_a": true,
    "switch_b": false,
    "door_main": false
  },
  "completion": {
    "levelComplete": false
  }
}
```

## Network messages

### Client -> server

- `join_room`
- `player_ready`
- `input`
- `restart_level`
- `request_next_level`

Example:

```json
{
  "type": "input",
  "input": {
    "left": true,
    "right": false,
    "up": false,
    "down": true,
    "interact": false
  }
}
```

### Server -> client

- `session`
- `room_state`
- `room_notice`
- `level_complete`
- `game_start`

## Embedding inside Dino Memo

Preferred approach:

- a separate web game client
- embedded in Streamlit with `components.html` or iframe

Recommended long-term shape:

- host the game client separately
- Streamlit passes:
  - room code
  - player name
  - PartyKit host

## Implementation order

### Phase 1

- add `Co-op Puzzle` tab
- room UI
- placeholder embedded client
- PartyKit room presence

### Phase 2

- local player movement
- synchronized remote player movement
- level 1

### Phase 3

- puzzle entities
- level 2 and 3
- level transitions

### Phase 4

- polish
- sound
- persistent progress

## Current repo plan

Add:

- `cooppuzzle-client/`
- PartyKit room protocol updates
- Streamlit tab for the game launcher

The first technical milestone is:

`Two users can join the same room and see both players moving on the same map in real time.`
