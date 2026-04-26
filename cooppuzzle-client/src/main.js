import Phaser from "phaser";

const query = new URLSearchParams(window.location.search);
const roomId = query.get("room") || "coop1";
const playerName = query.get("name") || "Player";
const partykitHost = query.get("host") || "";

class CoopScene extends Phaser.Scene {
  constructor() {
    super("coop");
    this.socket = null;
    this.connectionId = null;
    this.level = null;
    this.playerSprites = new Map();
    this.goalMarkers = [];
    this.cursors = null;
    this.keys = null;
    this.statusText = null;
  }

  create() {
    this.cameras.main.setBackgroundColor("#181109");
    this.add.text(24, 18, "Dino Memo Co-op Puzzle", {
      fontFamily: "Inter, system-ui, sans-serif",
      fontSize: "28px",
      color: "#fff4df",
    });

    this.statusText = this.add.text(24, 58, "Connecting...", {
      fontFamily: "Inter, system-ui, sans-serif",
      fontSize: "16px",
      color: "#d8c7a0",
      wordWrap: { width: 900 },
    });

    this.cursors = this.input.keyboard.createCursorKeys();
    this.keys = this.input.keyboard.addKeys("W,A,S,D");

    if (!partykitHost) {
      this.statusText.setText("Set a PartyKit host in the query string to start.");
      return;
    }

    this.connect();
    this.time.addEvent({
      delay: 110,
      loop: true,
      callback: () => {
        const move = this.currentMove();
        if (move.dx !== 0 || move.dy !== 0) {
          this.send("move_coop", move);
        }
      },
    });
  }

  connect() {
    const protocol = partykitHost.includes("localhost") ? "ws" : "wss";
    this.socket = new WebSocket(`${protocol}://${partykitHost}/party/coop-${roomId}`);
    this.socket.addEventListener("open", () => {
      this.statusText.setText(`Connected to room ${roomId}.`);
      this.send("join_coop", { displayName: playerName });
    });
    this.socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "session") {
        this.connectionId = payload.connectionId;
      }
      if (payload.type === "state" && payload.state?.coop) {
        this.renderCoop(payload.state.coop, payload.state.roomId);
      }
      if (payload.type === "notice") {
        this.statusText.setText(payload.message);
      }
    });
    this.socket.addEventListener("close", () => {
      this.statusText.setText("Disconnected from PartyKit.");
    });
  }

  send(type, payload = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify({ type, ...payload }));
  }

  currentMove() {
    let dx = 0;
    let dy = 0;
    if (this.cursors.left.isDown || this.keys.A.isDown) dx -= 1;
    if (this.cursors.right.isDown || this.keys.D.isDown) dx += 1;
    if (this.cursors.up.isDown || this.keys.W.isDown) dy -= 1;
    if (this.cursors.down.isDown || this.keys.S.isDown) dy += 1;
    return { dx, dy };
  }

  renderCoop(coop, serverRoomId) {
    const level = coop.level;
    const cellSize = 54;
    const originX = 140;
    const originY = 120;

    if (!this.level || this.level.index !== level.index) {
      this.level = level;
      this.children.removeAll();
      this.playerSprites.clear();
      this.add.text(24, 18, "Dino Memo Co-op Puzzle", {
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "28px",
        color: "#fff4df",
      });
      this.statusText = this.add.text(24, 58, "", {
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: "16px",
        color: "#d8c7a0",
        wordWrap: { width: 900 },
      });

      for (let y = 0; y < level.height; y += 1) {
        for (let x = 0; x < level.width; x += 1) {
          const isGoal =
            (x === level.goalA.x && y === level.goalA.y) ||
            (x === level.goalB.x && y === level.goalB.y);
          const tile = this.add.rectangle(
            originX + x * cellSize + cellSize / 2,
            originY + y * cellSize + cellSize / 2,
            cellSize - 2,
            cellSize - 2,
            isGoal ? 0x3f78aa : 0x24190c,
            isGoal ? 0.75 : 0.96
          );
          tile.setStrokeStyle(1, 0xfac63e, 0.12);
        }
      }
    }

    const players = Object.values(coop.players || {});
    players.forEach((player) => {
      let sprite = this.playerSprites.get(player.id);
      const px = originX + player.x * cellSize + cellSize / 2;
      const py = originY + player.y * cellSize + cellSize / 2;
      if (!sprite) {
        const rect = this.add.rectangle(px, py, cellSize - 16, cellSize - 16, Phaser.Display.Color.HexStringToColor(player.color).color);
        rect.setStrokeStyle(2, 0x111111, 0.5);
        const label = this.add.text(px, py, initials(player.name), {
          fontFamily: "Inter, system-ui, sans-serif",
          fontSize: "14px",
          color: "#111111",
        }).setOrigin(0.5);
        sprite = { rect, label };
        this.playerSprites.set(player.id, sprite);
      }
      sprite.rect.setPosition(px, py);
      sprite.label.setPosition(px, py);
    });

    for (const [id, sprite] of this.playerSprites.entries()) {
      if (!coop.players[id]) {
        sprite.rect.destroy();
        sprite.label.destroy();
        this.playerSprites.delete(id);
      }
    }

    const phase = coop.phase === "playing" ? "Live" : "Waiting";
    this.statusText.setText(
      `Room: ${serverRoomId} | Level: ${level.name} | Phase: ${phase}\n${coop.notice}`
    );
  }
}

function initials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "app",
  width: 960,
  height: 640,
  backgroundColor: "#181109",
  scene: [CoopScene],
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
});
