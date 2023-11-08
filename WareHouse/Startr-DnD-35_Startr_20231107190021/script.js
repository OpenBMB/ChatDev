document.getElementById("generate-button").addEventListener("click", generateMission);
function generateMission() {
    // Add your mission generation logic here
    var mission = generateRandomMission();
    openMissionInBrowser(mission);
}
function generateRandomMission() {
    // Add your random mission generation logic here
    var mission = "This is a randomly generated mission.";
    return mission;
}
function openMissionInBrowser(mission) {
    // Open the mission in a new browser tab
    var url = "https://example.com/mission?text=" + mission;
    window.open(url, "_blank");
}