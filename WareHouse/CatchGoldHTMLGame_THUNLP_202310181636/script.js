// Game Constants
const CANVAS_WIDTH = 800;
const CANVAS_HEIGHT = 600;
const CONTAINER_WIDTH = 100;
const CONTAINER_HEIGHT = 20;
const COIN_RADIUS = 10;
const COIN_SPEED = 3;
const COIN_VALUES = [1, 10, 100];
const GAME_DURATION = 15; // in seconds
// Game Variables
let canvas, ctx;
let containerX, containerY;
let coins = [];
let score = 0;
let gameStarted = false;
let gameTimer;
let gameOverScreen;
let finalScoreElement;
let restartButton;
let countdownElement;
let countdownTimer;
// Initialize the game
function init() {
    canvas = document.getElementById("gameCanvas");
    ctx = canvas.getContext("2d");
    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;
    containerX = CANVAS_WIDTH / 2 - CONTAINER_WIDTH / 2;
    containerY = CANVAS_HEIGHT - CONTAINER_HEIGHT;
    gameOverScreen = document.getElementById("gameOverScreen");
    finalScoreElement = document.getElementById("finalScore");
    restartButton = document.getElementById("restartButton");
    countdownElement = document.createElement("div");
    countdownElement.id = "countdown";
    document.body.appendChild(countdownElement);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);
    restartButton.addEventListener("click", restartGame);
    startGame();
}
// Start the game
function startGame() {
    gameStarted = true;
    score = 0;
    coins = [];
    countdownTimer = GAME_DURATION;
    gameTimer = setInterval(updateGame, 1000 / 60); // 60 FPS
    countdownElement.innerText = countdownTimer;
    setTimeout(endGame, GAME_DURATION * 1000);
}
// End the game
function endGame() {
    gameStarted = false;
    clearInterval(gameTimer);
    canvas.style.display = "none";
    gameOverScreen.style.display = "block";
    finalScoreElement.innerText = "Final Score: " + score;
}
// Restart the game
function restartGame() {
    canvas.style.display = "block";
    gameOverScreen.style.display = "none";
    init();
}
// Update the game state
function updateGame() {
    clearCanvas();
    updateContainer();
    updateCoins();
    renderContainer();
    renderCoins();
    renderScore();
    updateCountdown();
}
// Clear the canvas
function clearCanvas() {
    ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
}
// Update the container position based on user input
function updateContainer() {
    if (leftKeyPressed && containerX > 0) {
        containerX -= 5;
    }
    if (rightKeyPressed && containerX + CONTAINER_WIDTH < CANVAS_WIDTH) {
        containerX += 5;
    }
}
// Update the coin positions and check for collisions
function updateCoins() {
    for (let i = coins.length - 1; i >= 0; i--) {
        const coin = coins[i];
        coin.y += COIN_SPEED;
        if (coin.y + COIN_RADIUS > containerY && coin.x > containerX && coin.x < containerX + CONTAINER_WIDTH) {
            coins.splice(i, 1);
            score += coin.value;
        }
        if (coin.y + COIN_RADIUS > CANVAS_HEIGHT) {
            coins.splice(i, 1);
        }
    }
    if (Math.random() < 0.02) {
        const coin = {
            x: Math.random() * (CANVAS_WIDTH - COIN_RADIUS * 2) + COIN_RADIUS,
            y: -COIN_RADIUS,
            value: COIN_VALUES[Math.floor(Math.random() * COIN_VALUES.length)]
        };
        coins.push(coin);
    }
}
// Render the container
function renderContainer() {
    ctx.fillStyle = "blue";
    ctx.fillRect(containerX, containerY, CONTAINER_WIDTH, CONTAINER_HEIGHT);
}
// Render the coins
function renderCoins() {
    ctx.fillStyle = "gold";
    for (const coin of coins) {
        ctx.beginPath();
        ctx.arc(coin.x, coin.y, COIN_RADIUS, 0, 2 * Math.PI);
        ctx.fill();
    }
}
// Render the score
function renderScore() {
    ctx.fillStyle = "black";
    ctx.font = "20px Arial";
    ctx.fillText("Score: " + score, 10, 30);
}
// Update the countdown timer
function updateCountdown() {
    countdownTimer -= 1 / 60;
    if (countdownTimer <= 0) {
        countdownTimer = 0;
    }
    countdownElement.innerText = Math.ceil(countdownTimer);
}
// Handle keydown events
let leftKeyPressed = false;
let rightKeyPressed = false;
function handleKeyDown(event) {
    if (event.key === "ArrowLeft") {
        leftKeyPressed = true;
    }
    if (event.key === "ArrowRight") {
        rightKeyPressed = true;
    }
}
// Handle keyup events
function handleKeyUp(event) {
    if (event.key === "ArrowLeft") {
        leftKeyPressed = false;
    }
    if (event.key === "ArrowRight") {
        rightKeyPressed = false;
    }
}
// Start the game when the page is loaded
window.onload = init;