function append_message(role, text, avatarUrl) {
  
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


  var parsedText = role === 'System' ? parseSystemMessage(text) : parseCodeBlocks(text, role);

  message_container.append(parsedText);

  var copyButton = $("<button></button>")
    .addClass("copy-button")
    .text("Copy")
    .click(function () {
      copyToClipboard(parsedText); // Call the copyToClipboard function
    });

  copyButton.click(function () {
    copyToClipboard(parsedText);
    copyButton.text("Copied"); 
    setTimeout(function () {
      copyButton.text("Copy"); 
    }, 5000); 
  });

  message_container.append(copyButton); // Append the copy button

  $("#chat-box").append(message_container);
}

function parseCodeBlocks(text, role) {
  var parts = text.split(/(```[\s\S]*?```)/g);
  var parsedText = $("<div></div>").addClass("message-text");
  parts.forEach(part => {
    if (part.startsWith("```") && role != "System") {
      var trimmedBlock = part.trim();
      var language = trimmedBlock.match(/^```(\w+)/);
      if (language) {
        language = language[1];
        var codeContent = trimmedBlock.replace(/^```(\w+)/, '').replace(/```$/, '');
        var codeBlockHTML = `
          <div class="code-block">
            <div class="code-block-header">${role} - ${language}</div>
            <pre class="language-${language} dark line-numbers" data-line><code>${hljs.highlightAuto(codeContent, [language]).value}</code></pre>
          </div>
        `;
        parsedText.append(codeBlockHTML);
      }
    } else {
      parsedText.append(marked(_.escape(part), {breaks: true}));
    }
  });
  return parsedText;
}


function get_new_messages() {

  $.getJSON("/get_messages", function (data) {
    var lastDisplayedMessageIndex = $("#chat-box .message-container").length;

    for (var i = lastDisplayedMessageIndex; i < data.length; i++) {
      var role = data[i].role;
      var text = data[i].text;
      var avatarUrl = data[i].avatarUrl;

      append_message(role, text, avatarUrl);

    }
  });
}

function parseSystemMessage(text) {
  var message = $("<div></div>").addClass("message-text").addClass("system-message");
  var firstLine = text.split('\n')[0];
  var collapsed = true;

  var messageContent = $("<div></div>").html(marked(firstLine, { breaks: true })).addClass("original-markdown");
  var originalMarkdown = $("<div></div>").html(marked(text, { breaks: true })).addClass("original-markdown");

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

function copyToClipboard(element) {
  // Create a temporary textarea element to hold the text
  var tempTextArea = document.createElement("textarea");
  tempTextArea.value = element.text();
  document.body.appendChild(tempTextArea);

  // Select and copy the text from the textarea
  tempTextArea.select();
  document.execCommand("copy");

  // Remove the temporary textarea
  document.body.removeChild(tempTextArea);
}



$(document).ready(function () {
  get_new_messages();
  setInterval(function () {
    get_new_messages();
  }, 1000);
});


