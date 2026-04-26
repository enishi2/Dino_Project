import type * as Party from "partykit/server";

type Quote = {
  id: string;
  sender: string;
  text: string;
  date: string;
  difficulty: number;
};

type GuessPlayer = {
  id: string;
  name: string;
  score: number;
};

type RoundState = {
  quoteId: string;
  text: string;
  correctSender: string;
  dateLabel: string;
  options: string[];
  guesses: Record<string, string>;
  reveal: boolean;
  lastCorrect: string | null;
};

type CoopPlayer = {
  id: string;
  name: string;
  color: string;
  x: number;
  y: number;
};

type CoopLevel = {
  index: number;
  name: string;
  width: number;
  height: number;
  spawnA: { x: number; y: number };
  spawnB: { x: number; y: number };
  goalA: { x: number; y: number };
  goalB: { x: number; y: number };
};

type CoopState = {
  phase: "waiting" | "playing";
  level: CoopLevel;
  players: Record<string, CoopPlayer>;
  notice: string;
};

type RoomState = {
  roomId: string;
  players: Record<string, GuessPlayer>;
  quotes: Quote[];
  options: string[];
  usedQuoteIds: string[];
  currentRound: RoundState | null;
  coop: CoopState;
};

const STORAGE_KEY = "dino-memo-room-state";
const COOP_COLORS = ["#7FC4FF", "#F7D154"];
const COOP_LEVELS: CoopLevel[] = [
  {
    index: 0,
    name: "Twin Switch",
    width: 12,
    height: 8,
    spawnA: { x: 1, y: 3 },
    spawnB: { x: 10, y: 3 },
    goalA: { x: 5, y: 1 },
    goalB: { x: 6, y: 1 },
  },
  {
    index: 1,
    name: "Split Paths",
    width: 12,
    height: 8,
    spawnA: { x: 2, y: 6 },
    spawnB: { x: 9, y: 6 },
    goalA: { x: 5, y: 1 },
    goalB: { x: 6, y: 1 },
  },
];

const defaultCoopState = (): CoopState => ({
  phase: "waiting",
  level: COOP_LEVELS[0],
  players: {},
  notice: "Waiting for two players.",
});

const defaultState = (roomId: string): RoomState => ({
  roomId,
  players: {},
  quotes: [],
  options: [],
  usedQuoteIds: [],
  currentRound: null,
  coop: defaultCoopState(),
});

export default class Server implements Party.Server {
  constructor(readonly room: Party.Room) {}

  readonly options = { hibernate: false };

  state: RoomState = defaultState("room");

  async onStart() {
    this.state = (await this.room.storage.get<RoomState>(STORAGE_KEY)) ?? defaultState(this.room.id);
    this.state.roomId = this.room.id;
    this.state.coop ??= defaultCoopState();
  }

  async onConnect(connection: Party.Connection) {
    connection.send(JSON.stringify({ type: "session", connectionId: connection.id }));
    connection.send(JSON.stringify({ type: "state", state: this.state }));
  }

  async onMessage(message: string | ArrayBuffer, sender: Party.Connection) {
    if (typeof message !== "string") {
      return;
    }
    const payload = JSON.parse(message);

    switch (payload.type) {
      case "join":
        await this.handleGuessJoin(sender, payload.displayName);
        return;

      case "seed_quotes":
        await this.handleSeedQuotes(payload);
        return;

      case "next_round":
        await this.handleNextRound();
        return;

      case "submit_guess":
        await this.handleSubmitGuess(sender, payload.answer);
        return;

      case "join_coop":
        await this.handleCoopJoin(sender, payload.displayName);
        return;

      case "move_coop":
        this.handleCoopMove(sender, payload.dx, payload.dy);
        return;

      case "reset_coop":
        await this.resetCoopLevel();
        return;

      case "next_coop_level":
        await this.advanceCoopLevel();
        return;
    }
  }

  async onClose(connection: Party.Connection) {
    let changed = false;

    const guessPlayer = this.state.players[connection.id];
    if (guessPlayer) {
      delete this.state.players[connection.id];
      changed = true;
      this.notice(`${guessPlayer.name} left the Guess Who room.`);
    }

    const coopPlayer = this.state.coop.players[connection.id];
    if (coopPlayer) {
      delete this.state.coop.players[connection.id];
      this.updateCoopPhase();
      changed = true;
      this.notice(`${coopPlayer.name} left the co-op room.`);
    }

    if (changed) {
      await this.persist();
      this.broadcastState();
    }
  }

  async onRequest() {
    return new Response("Dino Memo PartyKit room is online.", { status: 200 });
  }

  private async handleGuessJoin(sender: Party.Connection, displayName: string) {
    this.state.players[sender.id] = {
      id: sender.id,
      name: displayName || "Player",
      score: this.state.players[sender.id]?.score ?? 0,
    };
    await this.persist();
    this.broadcastState();
    this.notice(`${displayName || "A player"} joined the Guess Who room.`);
  }

  private async handleSeedQuotes(payload: { quotes?: Quote[]; options?: string[] }) {
    if (!this.state.quotes.length && Array.isArray(payload.quotes) && payload.quotes.length) {
      this.state.quotes = payload.quotes
        .filter((quote: Quote) => quote && quote.text && quote.sender)
        .sort((left: Quote, right: Quote) => right.difficulty - left.difficulty);
      this.state.options = Array.isArray(payload.options)
        ? payload.options
        : [...new Set(this.state.quotes.map((q) => q.sender))];
      await this.persist();
      this.broadcastState();
    }
  }

  private async handleNextRound() {
    if (!this.state.quotes.length) {
      this.notice("This room has no quote deck yet.");
      return;
    }
    this.state.currentRound = this.makeRound();
    await this.persist();
    this.broadcastState();
  }

  private async handleSubmitGuess(sender: Party.Connection, answer: string) {
    if (!this.state.currentRound || this.state.currentRound.reveal) {
      return;
    }
    if (this.state.currentRound.guesses[sender.id]) {
      return;
    }
    this.state.currentRound.guesses[sender.id] = answer;
    if (answer === this.state.currentRound.correctSender) {
      if (this.state.players[sender.id]) {
        this.state.players[sender.id].score += 1;
      }
      this.state.currentRound.lastCorrect = sender.id;
    }
    if (Object.keys(this.state.currentRound.guesses).length >= Math.max(1, Object.keys(this.state.players).length)) {
      this.state.currentRound.reveal = true;
    }
    await this.persist();
    this.broadcastState();
  }

  private async handleCoopJoin(sender: Party.Connection, displayName: string) {
    const existing = this.state.coop.players[sender.id];
    if (existing) {
      existing.name = displayName || existing.name;
      this.updateCoopPhase();
      await this.persist();
      this.broadcastState();
      return;
    }

    if (Object.keys(this.state.coop.players).length >= 2) {
      sender.send(JSON.stringify({ type: "notice", message: "This co-op room is full." }));
      return;
    }

    const slot = Object.keys(this.state.coop.players).length;
    const spawn = slot === 0 ? this.state.coop.level.spawnA : this.state.coop.level.spawnB;
    this.state.coop.players[sender.id] = {
      id: sender.id,
      name: displayName || `Player ${slot + 1}`,
      color: COOP_COLORS[slot] || "#ffffff",
      x: spawn.x,
      y: spawn.y,
    };
    this.updateCoopPhase();
    await this.persist();
    this.broadcastState();
    this.notice(`${displayName || "A player"} joined the co-op room.`);
  }

  private handleCoopMove(sender: Party.Connection, dx: number, dy: number) {
    const player = this.state.coop.players[sender.id];
    if (!player) {
      return;
    }
    const nextX = clamp(player.x + normalizeStep(dx), 0, this.state.coop.level.width - 1);
    const nextY = clamp(player.y + normalizeStep(dy), 0, this.state.coop.level.height - 1);
    if (nextX === player.x && nextY === player.y) {
      return;
    }
    player.x = nextX;
    player.y = nextY;

    if (this.isCoopLevelComplete()) {
      this.state.coop.notice = "Level complete. Press next level.";
    } else {
      this.state.coop.notice =
        this.state.coop.phase === "playing"
          ? "Reach the two blue goal cells together."
          : "Waiting for two players.";
    }

    this.broadcastState();
  }

  private async resetCoopLevel() {
    const ids = Object.keys(this.state.coop.players);
    ids.forEach((playerId, index) => {
      const spawn = index === 0 ? this.state.coop.level.spawnA : this.state.coop.level.spawnB;
      this.state.coop.players[playerId].x = spawn.x;
      this.state.coop.players[playerId].y = spawn.y;
    });
    this.updateCoopPhase();
    await this.persist();
    this.broadcastState();
  }

  private async advanceCoopLevel() {
    if (!this.isCoopLevelComplete()) {
      return;
    }
    const nextIndex = (this.state.coop.level.index + 1) % COOP_LEVELS.length;
    this.state.coop.level = COOP_LEVELS[nextIndex];
    await this.resetCoopLevel();
  }

  private updateCoopPhase() {
    const playerCount = Object.keys(this.state.coop.players).length;
    this.state.coop.phase = playerCount >= 2 ? "playing" : "waiting";
    this.state.coop.notice =
      playerCount >= 2 ? "Reach the two blue goal cells together." : "Waiting for two players.";
  }

  private isCoopLevelComplete(): boolean {
    const players = Object.values(this.state.coop.players);
    if (players.length < 2) {
      return false;
    }
    const [first, second] = players;
    const goalA = this.state.coop.level.goalA;
    const goalB = this.state.coop.level.goalB;
    const aMatches =
      first.x === goalA.x && first.y === goalA.y && second.x === goalB.x && second.y === goalB.y;
    const bMatches =
      second.x === goalA.x && second.y === goalA.y && first.x === goalB.x && first.y === goalB.y;
    return aMatches || bMatches;
  }

  private makeRound(): RoundState {
    let available = this.state.quotes.filter((quote) => !this.state.usedQuoteIds.includes(quote.id));
    if (!available.length) {
      this.state.usedQuoteIds = [];
      available = [...this.state.quotes];
    }
    const hardPool = available.slice(0, Math.max(8, Math.ceil(available.length * 0.35)));
    const chosen = hardPool[Math.floor(Math.random() * hardPool.length)];
    this.state.usedQuoteIds = [chosen.id, ...this.state.usedQuoteIds].slice(0, 40);
    return {
      quoteId: chosen.id,
      text: chosen.text,
      correctSender: chosen.sender,
      dateLabel: chosen.date,
      options: this.state.options,
      guesses: {},
      reveal: false,
      lastCorrect: null,
    };
  }

  private broadcastState() {
    this.room.broadcast(JSON.stringify({ type: "state", state: this.state }));
  }

  private notice(message: string) {
    this.room.broadcast(JSON.stringify({ type: "notice", message }));
  }

  private async persist() {
    await this.room.storage.put(STORAGE_KEY, this.state);
  }
}

function normalizeStep(value: unknown): number {
  const number = typeof value === "number" ? value : 0;
  if (number > 0) {
    return 1;
  }
  if (number < 0) {
    return -1;
  }
  return 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
