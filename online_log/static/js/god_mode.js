const coordSet = [];
coordSet["Chief Executive Officer"] = {
  character: "Chief Executive Officer",
  imgid: "right",
  top: "-315px",
  left: "280px",
};
coordSet["Chief Product Officer"] = {
  character: "Chief Product Officer",
  imgid: "left",
  top: "-165px",
  left: "110px",
};
coordSet["Chief Human Resource Officer"] = {
  character: "Chief Human Resource Officer",
  imgid: "left",
  top: "-305px",
  left: "55px",
};
coordSet["Code Reviewer"] = {
  character: "Code Reviewer",
  imgid: "left",
  top: "-185px",
  left: "500px",
};
coordSet["Programmer"] = {
  character: "Programmer",
  imgid: "right",
  top: "-80px",
  left: "300px",
};
coordSet["Chief Technology Officer"] = {
  character: "Chief Technology Officer",
  imgid: "right",
  top: "-130px",
  left: "340px",
};
coordSet["Chief Creative Officer"] = {
  character: "Chief Creative Officer",
  imgid: "right",
  top: "-95px",
  left: "205px",
};
coordSet["Software Test Engineer"] = {
  character: "Software Test Engineer",
  imgid: "right",
  top: "-90px",
  left: "470px",
};
coordSet["User"] = {
  character: "User",
  imgid: "left",
  top: "-465px",
  left: "125px",
};
coordSet["Counselor"] = {
  character: "Counselor",
  imgid: "right",
  top: "-360px",
  left: "420px",
};
coordSet["Prompt Engineer"] = {
  character: "Prompt Engineer",
  imgid: "right",
  top: "-320px",
  left: "20px",
};
const Softwareinfo = {
  duration: "-1",
  cost: "-1",
  version_updates: "-1",
  num_code_files: "-1",
  num_png_files: "-1",
  num_doc_files: "-1",
  code_lines: "-1",
  env_lines: "-1",
  manual_lines: "-1",
  num_utterances: "-1",
  num_self_reflections: "-1",
  num_prompt_tokens: "-1",
  num_completion_tokens: "-1",
  num_total_tokens: "-1",
};

//control chars appear speed
var timeinterval = 5;
var charinterval = 1;
var scrollinterval = 40;

var contents;
var filename;
var curdialog = "";
var total_height = 0;

var cur_para = "";
var cur_command = "";
var idx = 0;
var dialog;

var replaying = 0;
var if_stop = 0;
let isPaused = false;
let pauseIntervalId;
var if_move = true;

/**
 * Handle the god message submission form
 */
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("message-input-form");
  form.addEventListener("submit", function (event) {
    event.preventDefault(); // Prevent the default form submission behavior

    const formData = new FormData(form);

    // Send the form data to the server using AJAX
    fetch("/send_god_message", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.text())
      .then((data) => {
        // Handle the server response (if needed)
        console.log(data);

        // Clear the form
        form.reset();
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  });
});

//watch lgtm button clicked
const lgtmButton = document.getElementById("lgtm");
lgtmButton.addEventListener("click", (event) => {
  event.preventDefault();
  var formData = new FormData();
  formData.append("god-message", "LGTM");

  fetch("/send_god_message", {
    method: "POST",
    body: formData,
  })
    .then((response) => response.text())
    .then((data) => {
      console.log(data);
    })
    .catch((error) => {
      console.error("Error:", error);
    });
});

const resumeButton = document.getElementById("resume");
resumeButton.addEventListener("click", (event) => {
  event.preventDefault();
  fetch("/start_working", {
    method: "POST",
    body: {},
  })
    .then((response) => response.text())
    .then((data) => {
      console.log(data);
    })
    .catch((error) => {
      console.error("Error:", error);
    });
});

const dialogbody = document.getElementById("dialogBody");
dialogbody.addEventListener("mousewheel", handleMouseWheel, false);

function handleMouseWheel(event) {
  if (event.wheelDelta > 0) {
    if_move = false;
  } else if (event.wheelDelta < 0) {
    if (
      dialogbody.scrollTop + dialogbody.clientHeight ==
      dialogbody.scrollHeight
    ) {
      if_move = true;
    }
  }
}

// JavaScript to show the modal when the page loads
document.addEventListener("DOMContentLoaded", function () {
  const modal = document.getElementById("new-request-modal");
  modal.style.display = "block";
});

// JavaScript to handle form submission
document.addEventListener("DOMContentLoaded", function () {
  const modalForm = document.getElementById("modal-form");

  modalForm.addEventListener("submit", function (event) {
    event.preventDefault();

    // Serialize form data to send to the server
    const formData = new FormData(modalForm);

    fetch("/start_new_project", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.text())
      .then((data) => {
        // Handle the server response (if needed)
        console.log(data);

        // Close the modal
        const modal = document.getElementById("new-request-modal");
        modal.style.display = "none";
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  });
});

function closeModal() {
  const modal = document.getElementById('new-request-modal');
  modal.style.display = 'none';
}

function updateSoftwareInfo(text) {
  // If the message contains the software info, update the software info
  if (text.indexOf('**[Software Info]**') > -1) {
    const info = text.split('**[Software Info]**:\n\n')[1];
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

    var temp_label = "";
    for (var information in Softwareinfo) {
      temp_label = document.getElementById(information);
      if (Softwareinfo[information] != "-1" && Softwareinfo[information] != "-1s") {
        temp_label.innerHTML = Softwareinfo[information];
      }
    }
  }
}

function append_message(role, text, avatarUrl) {
  updateSoftwareInfo(text);
  var message_container = $("<div></div>").addClass("message-container");
  var avatar_element = $("<span></span>").addClass("avatar");
  var role_element = $("<p></p>").addClass("role").text(role);

  if (avatarUrl) {
    avatar_element.css("background-image", `url(${avatarUrl})`);
  } else {
    avatar_element.css("background-color", "green");
  }

  message_container.append(role_element);
  message_container.append(avatar_element);

  var parsedText =
    role === "System" ? parseSystemMessage(text) : parseCodeBlocks(text, role);

  message_container.append(parsedText);

  $("#dialogBody").append(message_container);
}

function parseCodeBlocks(text, role) {
  var parts = text.split(/(```[\s\S]*?```)/g);
  var parsedText = $("<div></div>").addClass("message-text");
  parts.forEach((part) => {
    if (part.startsWith("```") && role != "System") {
      var trimmedBlock = part.trim();
      var language = trimmedBlock.match(/^```(\w+)/);
      if (language) {
        language = language[1];
        var codeContent = trimmedBlock
          .replace(/^```(\w+)/, "")
          .replace(/```$/, "");
        var codeBlockHTML = `
            <div class="code-block">
              <div class="code-block-header">${role} - ${language}</div>
              <pre class="language-${language} dark line-numbers" data-line><code>${
          hljs.highlightAuto(codeContent, [language]).value
        }</code></pre>
            </div>
          `;
        parsedText.append(codeBlockHTML);
      }
    } else {
      parsedText.append(marked(_.escape(part), { breaks: true }));
    }
  });
  return parsedText;
}

function get_new_messages() {
  if (document.getElementById("Requesttext").innerHTML === 'Task: ') {
    $.getJSON("/project_description", function (data) {
      if (data && data.description) {
        document.getElementById("Requesttext").innerHTML = 'Task: ' + data.description;
      }
    });
  }
  $.getJSON("/get_messages", function (data) {
    var lastDisplayedMessageIndex = $("#dialogBody .message-container").length;

    for (var i = lastDisplayedMessageIndex; i < data.length; i++) {
      var role = data[i].role;
      var text = data[i].text;
      var avatarUrl = data[i].avatarUrl;

      append_message(role, text, avatarUrl);
    }
  });
}

function parseSystemMessage(text) {
  var message = $("<div></div>")
    .addClass("message-text")
    .addClass("system-message");
  var firstLine = text.split("\n")[0];
  var collapsed = true;

  var messageContent = $("<div></div>")
    .html(marked(firstLine, { breaks: true }))
    .addClass("original-markdown");
  var originalMarkdown = $("<div></div>")
    .html(marked(text, { breaks: true }))
    .addClass("original-markdown");

  var expandButton = $("<button></button>")
    .addClass("expand-button")
    .text("Expand")
    .click(function () {
      if (collapsed) {
        messageContent.hide();
        originalMarkdown.show();
        expandButton.text("Collapse");
      } else {
        messageContent.show();
        originalMarkdown.hide();
        expandButton.text("Expand");
      }
      collapsed = !collapsed;
    });

  message.append(messageContent);
  message.append(originalMarkdown);
  message.append(expandButton);

  originalMarkdown.hide();

  return message;
}

$(document).ready(function () {
  get_new_messages();
  setInterval(function () {
    get_new_messages();
  }, 1000);
});
