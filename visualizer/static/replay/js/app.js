const coordSet = [];
coordSet["Chief Executive Officer"] = {
    "character": "Chief Executive Officer",
    "imgid": "right",
    "top": "-315px",
    "left": "280px"
};
coordSet["Chief Product Officer"] = {
    "character": "Chief Product Officer",
    "imgid": "left",
    "top": "-165px",
    "left": "110px"
};
coordSet["Chief Human Resource Officer"] = {
    "character": "Chief Human Resource Officer",
    "imgid": "left",
    "top": "-305px",
    "left": "55px"
};
coordSet["Code Reviewer"] = {
    "character": "Code Reviewer",
    "imgid": "left",
    "top": "-185px",
    "left": "500px"
};
coordSet["Programmer"] = {
    "character": "Programmer",
    "imgid": "right",
    "top": "-80px",
    "left": "300px"
};
coordSet["Chief Technology Officer"] = {
    "character": "Chief Technology Officer",
    "imgid": "right",
    "top": "-130px",
    "left": "340px"
};
coordSet["Chief Creative Officer"] = {
    "character": "Chief Creative Officer",
    "imgid": "right",
    "top": "-95px",
    "left": "205px"
}
coordSet["Software Test Engineer"] = {
    "character": "Software Test Engineer",
    "imgid": "right",
    "top": "-90px",
    "left": "470px"

}
coordSet["User"] = {
    "character": "User",
    "imgid": "left",
    "top": "-465px",
    "left": "125px"
}
coordSet["Counselor"] = {
    "character": "Counselor",
    "imgid": "right",
    "top": "-360px",
    "left": "420px"
}
coordSet["Prompt Engineer"] = {
    "character": "Prompt Engineer",
    "imgid": "right",
    "top": "-320px",
    "left": "20px"
}
coordSet["System"] = {
    "character": "System",
    "imgid": "left",
    "top": "-405px",
    "left": "20px"
}
coordSet["HTTP Request"] = {
    "character": "HTTP Request",
    "imgid": "right",
    "top": "-405px",
    "left": "20px"
}

const Softwareinfo = {
    "duration": "-1",
    "cost": "-1",
    "version_updates": "-1",
    "num_code_files": "-1",
    "num_png_files": "-1",
    "num_doc_files": "-1",
    "code_lines": "-1",
    "env_lines": "-1",
    "manual_lines": "-1",
    "num_utterances": "-1",
    "num_self_reflections": "-1",
    "num_prompt_tokens": "-1",
    "num_completion_tokens": "-1",
    "num_total_tokens": "-1",
};

//control chars appear speed
var timeinterval = 5;
var charinterval = 1;
var scrollinterval = 40;

var contents;
var filename;
var curdialog = '';
var total_height = 0;

var cur_para = '';
var cur_command = '';
var idx = 0;
var dialog;

var replaying = 0;
var if_stop = 0;
let isPaused = false;
let pauseIntervalId;
var if_move = true;
var md = window.markdownit();

//watch replay button clicked
const button = document.getElementById('replay');
button.addEventListener('click', () => {
    replayDialog(idx);
});

$(document).ready(function() {
    $('#filebutton').click(function() {
        $('#fileInput').click();
    });

});

const dialogbody = document.getElementById("dialogBody");
dialogbody.addEventListener("mousewheel", handleMouseWheel, false);

function handleMouseWheel(event) {
    if (event.wheelDelta > 0) {
        if_move = false;
    } else if (event.wheelDelta < 0) {
        if (dialogbody.scrollTop + dialogbody.clientHeight == dialogbody.scrollHeight) {
            if_move = true;
        }
    }
}

function getinterval(speed) {

    if (speed < 80 && speed > 40) {
        timeinterval = 250 / speed;
        charinterval = 2;
        scrollinterval = 80;
    } else if (speed <= 40 && speed > 0) {
        timeinterval = 150 / speed;
        charinterval = 1;
        scrollinterval = 80;
    } else if (speed >= 80 && speed < 90) {
        timeinterval = 100 / speed;
        charinterval = 1;
        scrollinterval = 100;
    } else if (speed >= 90 && speed <= 100) {
        timeinterval = 5 / speed;
        charinterval = 1;
        scrollinterval = 400;
    }
}
//use the slider to control the replay speed
function speedchange() {
    var speedbar = document.getElementById("speed");
    var speed = speedbar.value;
    if (speed == 0) {
        if (!isPaused) {
            isPaused = true;
            clearInterval(pauseIntervalId);
            updateCompanyWorking("end");
        }
    } else if (speed != 0 && isPaused == true) {
        getinterval(speed);
        isPaused = false;
        idx += 1;
        replayDialog(idx);
    } else if (speed != 0) {
        isPaused = false;
        getinterval(speed);
    }
}
// do replay
async function replayDialog(idx) {
    if (replaying == 1 && idx == 0) {
        return;
    }
    if (idx == 0) {
        replaying = 1;
        console.log("Attempting to replay");
        dialog = extraction(contents);
        var filelable = document.getElementById("successupload");
        filelable.style.display = "block";
        var info = "Replaying `" + filename + "` ......";
        filelable.innerHTML = md.render(info);
    }
    for (let i = idx; i < dialog.length; ++i) {
        await createPara(dialog[i], i);
    }
}

//watch .log file input
function watchfileInput(files) {
    if (files.length) {
        const file = files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function() {
                contents = this.result;
            };
            reader.readAsText(file);
            var filelable = document.getElementById("successupload");
            filelable.style.display = "block";
            var info = "File uploaded (`" + file.name + "`). Please click **\"Replay\"** to show Startr.Team's development process";
            filename = file.name;
            filelable.innerHTML = md.render(info);
        }
    }
}

function extraction(contents) {
    console.log("Starting extraction process...");

    // Updated regex to capture log entries with the correct format
    const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.*?)$/gm;

    var matches = [];
    let match;

    while ((match = regex.exec(contents)) !== null) {
        const timestamp = match[1];
        const level = match[2];
        const text = match[3];
        matches.push({ timestamp, level, text });
    }

    console.log("Total matches found: ", matches.length);

    const dialog = [];
    let count = 0;

    // Simplified regex patterns for different log entry types
    const regex_assistant = /(.*?): (.*)/s;
    const regex_user = /(.*?): (.*)/s;
    const regex_start = /Startr.Team Starts/s;
    const regex_end = /Startr.Team Ends/s;
    const regex_task = /task_prompt: (.*)/s;
    const regex_info = /Software Info:([\s\S]*)/s;

    for (let i = 0; i < matches.length; i++) {
        const { timestamp, text } = matches[i];
        console.log(`Processing match ${i + 1}/${matches.length} - Timestamp: ${timestamp}`);
        console.log(`Text content: ${text}`);

        let if_break = false;

        if (regex_start.test(text)) {
            console.log("Matched start of session");
            dialog.push({
                start: "Startr.Team Starts",
            });
            if_break = true;
        }

        if (regex_end.test(text)) {
            console.log("Matched end of session");
            dialog.push({
                end: "Startr.Team Ends",
            });
            if_break = true;
        }

        if ((match = regex_assistant.exec(text)) !== null) {
            console.log("Matched assistant dialog:", match[2]);
            dialog.push({
                type: "assistant",
                character: match[1],
                command: match[2],
                len: match[2].length,
                count: ++count
            });
            if_break = true;
        }

        if ((match = regex_user.exec(text)) !== null) {
            console.log("Matched user dialog:", match[2]);
            dialog.push({
                type: "user",
                character: match[1],
                command: match[2],
                len: match[2].length,
                count: ++count
            });
            if_break = true;
        }

        if ((match = regex_task.exec(text)) !== null) {
            console.log("Matched task:", match[1]);
            dialog.push({
                task: match[1]
            });
            if_break = true;
        }

        if ((match = regex_info.exec(text)) !== null) {
            console.log("Matched software info");
            const info = match[1];
            const Softwareinfo = {};
            
            const extractInfo = (pattern, key) => {
                const res = new RegExp(pattern).exec(info);
                if (res) {
                    Softwareinfo[key] = res[1];
                    console.log(`Extracted ${key}: ${Softwareinfo[key]}`);
                }
            };

            extractInfo(/code_lines\s*=\s*(\d+)/, "code_lines");
            extractInfo(/num_code_files\s*=\s*(\d+)/, "num_code_files");
            extractInfo(/num_png_files\s*=\s*(\d+)/, "num_png_files");
            extractInfo(/num_doc_files\s*=\s*(\d+)/, "num_doc_files");
            extractInfo(/env_lines\s*=\s*(\d+)/, "env_lines");
            extractInfo(/manual_lines\s*=\s*(\d+)/, "manual_lines");
            extractInfo(/duration\s*=\s*(\d+(\.\d+)?s)/, "duration");
            extractInfo(/num_utterances\s*=\s*(\d+)/, "num_utterances");
            extractInfo(/num_self_reflections\s*=\s*(\d+)/, "num_self_reflections");
            extractInfo(/num_prompt_tokens\s*=\s*(\d+)/, "num_prompt_tokens");
            extractInfo(/num_completion_tokens\s*=\s*(\d+)/, "num_completion_tokens");
            extractInfo(/num_total_tokens\s*=\s*(\d+)/, "num_total_tokens");
            extractInfo(/cost\s*=\s*([\d.]+)/, "cost");
            extractInfo(/version_updates\s*=\s*(\d+)/, "version_updates");

            dialog.push({ info, Softwareinfo });
            if_break = true;
        }

        if (!if_break) {
            console.log("No match found for this entry.");
        }
    }

    console.log("Extraction complete. Total dialogs extracted:", dialog.length);
    return dialog;
}



//show dailog
function createPara(d, i) {
    const singleDialog = document.createElement("div");
    singleDialog.style.position = "relative";
    curdialog = singleDialog;
    singleDialog.style.display = "flex";
    singleDialog.style.flexDirection = "column";
    singleDialog.style.width = "96%";
    dialogbody.appendChild(singleDialog);
    var paralen;
    if (d.type && d.character) {
        updateCompanyWorking(d.character);
        var renderedHtml = md.render(d.character);
        const character = document.createElement("div");
        character.style.display = "flex";

        character.style.backgroundColor = "lightblue";
        character.style.width = "fit-content";
        character.style.padding = "5px 20px";
        character.style.marginBottom = "5px";
        character.style.fontSize = "13px ";
        character.style.border = "1px solid rgba(11, 20, 150, .3)";
        character.style.borderRadius = "10px";
        character.style.boxShadow = "2px 2px 2px black";
        character.style.fontFamily = "'Lucida Sans', 'Lucida Sans Regular', 'Lucida Grande', 'Lucida Sans Unicode', Geneva, Verdana, sans-serif;";

        if (d.type == "user") {
            character.style.position = "relative";
            character.style.marginLeft = "auto";
        }
        character.innerHTML = renderedHtml;
        singleDialog.appendChild(character);

        const characterimg = document.createElement("img");
        console.log(d.character);
        if (d.character == "Programmer") {
            characterimg.src = "figures/programmer.png";
        } else if (d.character == "System") {
            characterimg.src = "figures/System.png";
        } else if (d.character == "HTTP Request") {
            characterimg.src = "figures/http.png";
        } else if (d.character == "Code Reviewer") {
            characterimg.src = "figures/reviewer.png";
        } else if (d.character == "Chief Human Resource Officer") {
            characterimg.src = "figures/hr.png";
        } else if (d.character == "Chief Executive Officer") {
            characterimg.src = "figures/ceo.png";
        } else if (d.character == "Chief Product Officer") {
            characterimg.src = "figures/cpo.png";
        } else if (d.character == "Chief Technology Officer") {
            characterimg.src = "figures/cto.png";
        } else if (d.character == "Chief Creative Officer") {
            characterimg.src = "figures/designer.png";
        } else if (d.character == "Software Test Engineer") {
            characterimg.src = "figures/tester.png";
        } else if (d.character == "User") {
            characterimg.src = "figures/user.png";
        } else if (d.character == "Counselor") {
            characterimg.src = "figures/counselor.png";
        } else if (d.character == "Prompt Engineer") {
            characterimg.src = "figures/pe.png";
        }

        characterimg.style.height = "40px";
        characterimg.style.width = "30px";
        characterimg.style.position = "relative";
        characterimg.style.marginLeft = "10px";
        character.appendChild(characterimg);
        character.style.width = "fit-content";


        var renderedHtml = md.render(d.command);
        const paragraph = document.createElement("div");
        paragraph.className = "markdown-body";
        //paragraph.innerHTML = renderedHtml;
        paragraph.style.padding = "10px";
        paragraph.style.border = "3px solid #a08D8D";
        paragraph.style.width = "750px";
        paragraph.style.marginLeft = "0.4rem";
        paragraph.style.border = "1px solid rgba(11, 20, 150, .3)";
        paragraph.style.borderRadius = "10px";
        paragraph.style.boxShadow = "2px 2px 2px black";

        singleDialog.appendChild(paragraph);

        const emptyparagraph = document.createElement("div");
        emptyparagraph.style.height = "10px";
        singleDialog.appendChild(emptyparagraph);

        if (d.type == "user") {
            paragraph.style.backgroundColor = "#a02D8D";
        } else {
            paragraph.style.backgroundColor = "#133153";
        }
        cur_command = d.command;
        cur_para = paragraph;
        idx = i;
        return Promise.resolve(printCommand(paragraph, d.command));

    } else if (d.start) {
        paralen = 0;
        var renderedHtml = md.render("----------" + d.start + "----------");
        const starttext = document.createElement("div");
        starttext.innerHTML = renderedHtml;
        singleDialog.appendChild(starttext);

    } else if (d.end) {
        paralen = 0;
        updateCompanyWorking("end");
        var renderedHtml = md.render("----------" + d.end + "----------");
        const endtext = document.createElement("div");
        endtext.innerHTML = renderedHtml;
        singleDialog.appendChild(endtext);
        var filelable = document.getElementById("successupload");
        filelable.style.display = "block";
        var info = "Replayed";
        filelable.innerHTML = md.render(info);
    } else if (d.task) {
        var renderedHtml = md.render("Task:    " + d.task);
        const tasktext = document.getElementById("Requesttext");
        tasktext.innerHTML = renderedHtml;
    } else if (d.info) {
        var renderedHtml = md.render(d.info);
        const infotext = document.getElementById("dialogStatistic");
        var temp_label = "";
        for (var c in Softwareinfo) {
            temp_label = document.getElementById(c);
            if (Softwareinfo[c] != "-1" && Softwareinfo[c] != "-1s") {
                temp_label.innerHTML = Softwareinfo[c];
            }
        }
    }
}

//update company image
function updateCompanyWorking(character) {
    if (character === "end") {
        var img1 = document.getElementById("right");
        var img2 = document.getElementById("left");
        if (img1) img1.style.display = "none";
        if (img2) img2.style.display = "none";
        return;
    }

    const characterConfig = coordSet[character];
    if (!characterConfig) {
        console.error(`Character '${character}' is not defined in coordSet.`);
        return;
    }

    var imgid = characterConfig.imgid;
    var left_bias = characterConfig.left;
    var top_bias = characterConfig.top;
    var img = document.getElementById(imgid);

    if (!img) {
        console.error(`Image element with id '${imgid}' not found.`);
        return;
    }

    img.style.display = "block";
    img.style.left = left_bias;
    img.style.top = top_bias;

    var another_img = document.getElementById(imgid === "left" ? "right" : "left");
    if (another_img) another_img.style.display = "none";
}

async function updateParashow(container, command, index, len) {
    var cur_content;
    if (index == len - 1) {
        cur_content = command.slice(0, index);
    }
    if (index < len) {
        cur_content = command.slice(0, index);
        if (cur_content != null && cur_content != undefined) {
            container.innerHTML = md.render(cur_content);
        };
    }
    if (index % (scrollinterval) == 0 && if_move == true) {
        if (curdialog != null && curdialog != '') {
            const newBoxRect = curdialog.getBoundingClientRect();
            total_height += newBoxRect.height;
            dialogbody.scrollTo({ top: total_height, behavior: 'smooth' });
        }
    }
}

async function printCommand(paragraph, command) {
    var paralen = command.length;
    const tasks = [];

    for (let j = 0; j < paralen; j = j + charinterval) {
        tasks.push(new Promise(resolve => {
            pauseIntervalId = setTimeout(() => {
                updateParashow(paragraph, command, j, paralen);
                resolve();
            }, timeinterval * j);
        }));

        if (isPaused) {
            await Promise.all(tasks);
        }
    }
    await Promise.all(tasks);
    return 1;
}