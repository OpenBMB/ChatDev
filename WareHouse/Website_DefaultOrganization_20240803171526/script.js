var countdownElement = document.getElementById("countdown");
var countdownInterval;
function startTimer() {
    var time = prompt("Enter the time in seconds:");
    if (time) {
        var seconds = parseInt(time);
        if (!isNaN(seconds) && seconds > 0) {
            clearInterval(countdownInterval);
            countdownInterval = setInterval(function() {
                if (seconds <= 0) {
                    clearInterval(countdownInterval);
                    playSound();
                } else {
                    var hours = Math.floor(seconds / 3600);
                    var minutes = Math.floor((seconds % 3600) / 60);
                    var remainingSeconds = seconds % 60;
                    countdownElement.innerHTML = formatTime(hours) + ":" + formatTime(minutes) + ":" + formatTime(remainingSeconds);
                    seconds--;
                }
            }, 1000);
        } else {
            alert("Invalid input. Please enter a positive number.");
            clearInterval(countdownInterval); // Stop the timer when an invalid input is entered
        }
    }
}
function stopTimer() {
    clearInterval(countdownInterval);
    countdownElement.innerHTML = "00:00:00";
}
function formatTime(time) {
    return time < 10 ? "0" + time : time;
}
function playSound() {
    var audio = new Audio("sound.mp3");
    audio.play();
}