# PartyKit Multiplayer

This project now includes a first PartyKit server for realtime `Guess Who Said It` rooms.

Files:

- [partykit/package.json](</C:/Naydino Project/partykit/package.json>)
- [partykit/partykit.json](</C:/Naydino Project/partykit/partykit.json>)
- [partykit/src/server.ts](</C:/Naydino Project/partykit/src/server.ts>)

## What it does

- creates realtime rooms
- keeps room state in PartyKit storage
- tracks players and scores
- serves harder quotes first by biasing rounds toward the top difficulty slice
- reveals the correct answer after all connected players submit a guess

## How Dino Memo uses it

The Streamlit app has a new `Multiplayer` tab.

To enable it, set:

```powershell
$env:PARTYKIT_HOST="your-project.yourname.partykit.dev"
```

The tab sends a prefiltered quote deck from the loaded conversation to the PartyKit room. The first player in a room seeds the quote deck, and everyone in that room plays the same live rounds.

## Local dev

From the `partykit` folder:

```powershell
npm install
npx partykit dev src/server.ts
```

## Deploy

From the `partykit` folder:

```powershell
npx partykit deploy src/server.ts
```

After deploy, copy the PartyKit host and set `PARTYKIT_HOST` in the environment where Dino Memo runs.

## Next hardening step

This first version focuses on realtime room state. The next security step should be authenticating PartyKit connections with the Supabase session JWT using `onBeforeConnect`, following PartyKit's authentication guide:

- [PartyKit authentication guide](https://docs.partykit.io/guides/authentication/)
