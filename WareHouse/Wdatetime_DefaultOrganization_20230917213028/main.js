document.getElementById("timezoneForm").addEventListener("submit", function(event) {
    event.preventDefault();
    var time = document.getElementById("time").value;
    var timezone = document.getElementById("timezone").value;
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/convert", true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            var convertedTime = JSON.parse(xhr.responseText).convertedTime;
            document.getElementById("convertedTime").innerText = convertedTime;
        }
    };
    xhr.send(JSON.stringify({ time: time, timezone: timezone }));
});