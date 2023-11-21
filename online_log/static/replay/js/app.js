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
            var info = "File uploaded (`" + file.name + "`). Please click **\"Replay\"** to show ChatDev's development process";
            filename = file.name;
            filelable.innerHTML = md.render(info);
        }
    }
}

//extract information
function extraction(contents) {
    const regex = /\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \w+)\] ([.\s\S\n\r\d\D\t]*?)(?=\n\[\d|$)/g;

    var matches = [];

    let match;
    var itemp = 0;
    while ((match = regex.exec(contents))) {
        console.log(itemp);
        itemp++;
        const timestamp = match[1];
        const text = match[2];
        matches.push({
            timestamp,
            text
        });
    }
    const regex_assistant = /(.*):([.\r\n\s\S\t\d\D]*)<->([.\r\n\s\S\t\d\D]*?)\]([.\r\n\s\S\t\d\D]*)/g;
    const regex_user = /(.*):(.*)(\[Start Chat\])([.\r\n\s\S\t\d\D]*?)\]([.\r\n\s\S\t\d\D]*)/g;
    const regex_prompt = /(Prompt Engineer):([\S\s]*)/g

    const regex_end = /(AgentTech Ends|ChatDev Ends)/g;
    const regex_start = /(ChatDev Starts)([\D\s])*(\d*)/g;

    const regex_task = /(task_prompt)(.*):(.*)/g;
    const regex_info = /Software Info([\r\n\s\S\t\d\D]*)/g;

    const regex_system = /System/g;
    const regex_debug = /DEBUG/g;

    var dialog = [];
    var count = 0;

    for (let i = 0; i < matches.length; ++i) {
        var if_break = false;
        console.log(i);
        if (i == 159 || i == 198 || i == 223 || i == 260 || i == 416 || i == 537) {
            //console.log(matches[i]);
        }
        while ((match = regex_debug.exec(matches[i].timestamp)) !== null) {
            if_break = true;
        }
        while ((match = regex_system.exec(matches[i].text)) !== null) {
            if_break = true;
        }
        while (((match = regex_prompt.exec(matches[i].text)) !== null)) {
            const type = "assitant";
            const character = match[1];
            const command = match[2];
            const len = match[2].length;
            count += 1;
            dialog.push({
                type,
                character,
                command,
                len,
                count
            });
            if_break = true;
        }
        if (if_break) {
            continue;
        }

        while ((match = regex_assistant.exec(matches[i].text)) !== null) {
            const type = "assitant";
            const character = match[1];
            const command = match[4];
            const len = match[4].length;
            count += 1;
            dialog.push({
                type,
                character,
                command,
                len,
                count
            });

        }
        while ((match = regex_user.exec(matches[i].text)) !== null) {
            const type = "user";
            const character = match[1];
            const command = match[5];
            const len = match[5].length;
            count += 1;
            dialog.push({
                type,
                character,
                command,
                len,
                count
            });
        }
        while ((match = regex_start.exec(matches[i].text)) !== null) {
            const start = match[1];
            const len = match[1].length;
            dialog.push({
                start,
                len,
            });

        }
        while ((match = regex_end.exec(matches[i].text)) !== null) {
            const end = match[1];
            const len = match[1].length;
            dialog.push({
                end,
                len,
            });

        }
        while ((match = regex_task.exec(matches[i].text)) !== null) {
            const task = match[3];
            dialog.push({
                task
            });

        }
        while ((match = regex_info.exec(matches[i].text)) !== null) {
            const info = match[1];
            if ((/code_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.code_lines = (/code_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_code_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_code_files = (/num_code_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_png_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_png_files = (/num_png_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_doc_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_doc_files = (/num_doc_files(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/env_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.env_lines = (/env_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/manual_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.manual_lines = (/manual_lines(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/duration(?:[\t\n\r\s\D]*?)=(-?(\d*)(.(\d)*)?s)/g).exec(info) != null) {
                Softwareinfo.duration = (/duration(?:[\t\n\r\s\D]*?)=(-?(\d*)(.(\d)*)?s)/g).exec(info)[1];
            }
            if ((/num_utterances(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_utterances = (/num_utterances(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_self_reflections(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_self_reflections = (/num_self_reflections(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_prompt_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_prompt_tokens = (/num_prompt_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_completion_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_completion_tokens = (/num_completion_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/num_total_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info) != null) {
                Softwareinfo.num_total_tokens = (/num_total_tokens(?:[\t\n\r\s\D]*?)=(-?(\d*))/g).exec(info)[1];
            }
            if ((/cost(?:[\t\n\r\s\D]*?)=(.((\d)*\.(\d)*))/g).exec(info) != null) {
                Softwareinfo.cost = (/cost(?:[\t\n\r\s\D]*?)=(.((\d)*\.(\d)*))/g).exec(info)[1];
            }
            if ((/version_updates(?:[\t\n\r\s\D]*?)=(-?\d*)/g).exec(info) != null) {
                Softwareinfo.version_updates = (/version_updates(?:[\t\n\r\s\D]*?)=(-?\d*)/g).exec(info)[1];
            }

            dialog.push({
                info,
                Softwareinfo
            });

        }
    }
    return dialog;
}

//show dailog
function createPara(d, i) {
    const singleDialog = document.createElement("div");
    singleDialog.style.position = "relative";
    curdialog = singleDialog;
    singleDialog.style.display = "flex";
    singleDialog.style.flexDirection = "column";
    singleDialog.style.width = "773px";
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
        paragraph.style.border = "1px solid rgba(11, 20, 150, .3)";
        paragraph.style.borderRadius = "10px";
        paragraph.style.boxShadow = "2px 2px 2px black";

        singleDialog.appendChild(paragraph);

        const emptyparagraph = document.createElement("div");
        emptyparagraph.style.height = "10px";
        singleDialog.appendChild(emptyparagraph);

        if (d.type == "user") {
            paragraph.style.backgroundColor = "#4b751a";
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
    if (character == "end") {
        var img1 = document.getElementById("right");
        img1.style.display = "none";
        var img2 = document.getElementById("left");
        img2.style.display = "none";
        return;
    }
    var imgid = coordSet[character].imgid;
    var left_bias = coordSet[character].left;
    var top_bias = coordSet[character].top;
    var img = document.getElementById(imgid);

    img.style.display = "block";
    img.style.left = left_bias;
    img.style.top = top_bias;

    if (imgid == "left") {
        var another_img = document.getElementById("right");
        another_img.style.display = "none";
    } else {
        var another_img = document.getElementById("left");
        another_img.style.display = "none";
    }
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