import type * as Party from "partykit/server";

type Quote = {
  id: string;
  sender: string;
  text: string;
  date: string;
  difficulty: number;
};

type Player = {
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

type RoomState = {
  roomId: string;
  players: Record<string, Player>;
  quotes: Quote[];
  options: string[];
  usedQuoteIds: string[];
  currentRound: RoundState | null;
};

const STORAGE_KEY = "guess-state";

const defaultState = (roomId: string): RoomState => ({
  roomId,
  players: {},
  quotes: [],
  options: [],
  usedQuoteIds: [],
  currentRound: null,
});

export default class Server implements Party.Server {
  constructor(readonly room: Party.Room) {}

  readonly options = { hibernate: false };

  state: RoomState = defaultState("room");

  async onStart() {
    this.state = (await this.room.storage.get<RoomState>(STORAGE_KEY)) ?? defaultState(this.room.id);
    this.state.roomId = this.room.id;
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
        this.state.players[sender.id] = {
          id: sender.id,
          name: payload.displayName || "Player",
          score: this.state.players[sender.id]?.score ?? 0,
        };
        await this.persist();
        this.broadcastState();
        this.notice(`${payload.displayName || "A player"} joined the room.`);
        return;

      case "seed_quotes":
        if (!this.state.quotes.length && Array.isArray(payload.quotes) && payload.quotes.length) {
          this.state.quotes = payload.quotes
            .filter((quote: Quote) => quote && quote.text && quote.sender)
            .sort((left: Quote, right: Quote) => right.difficulty - left.difficulty);
          this.state.options = Array.isArray(payload.options) ? payload.options : [...new Set(this.state.quotes.map((q) => q.sender))];
          await this.persist();
          this.broadcastState();
        }
        return;

      case "next_round":
        if (!this.state.quotes.length) {
          this.notice("This room has no quote deck yet.");
          return;
        }
        this.state.currentRound = this.makeRound();
        await this.persist();
        this.broadcastState();
        return;

      case "submit_guess":
        if (!this.state.currentRound || this.state.currentRound.reveal) {
          return;
        }
        if (this.state.currentRound.guesses[sender.id]) {
          return;
        }
        const playerId = sender.id;
        this.state.currentRound.guesses[playerId] = payload.answer;
        if (payload.answer === this.state.currentRound.correctSender) {
          if (this.state.players[playerId]) {
            this.state.players[playerId].score += 1;
          }
          this.state.currentRound.lastCorrect = playerId;
        }
        if (Object.keys(this.state.currentRound.guesses).length >= Math.max(1, Object.keys(this.state.players).length)) {
          this.state.currentRound.reveal = true;
        }
        await this.persist();
        this.broadcastState();
        return;
    }
  }

  async onClose(connection: Party.Connection) {
    const player = this.state.players[connection.id];
    if (player) {
      delete this.state.players[connection.id];
      await this.persist();
      this.broadcastState();
      this.notice(`${player.name} left the room.`);
    }
  }

  async onRequest() {
    return new Response("Dino Memo PartyKit room is online.", { status: 200 });
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
