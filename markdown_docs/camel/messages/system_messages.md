## ClassDef SystemMessage
**SystemMessage**: SystemMessage 类用于在 CAMEL 聊天系统中创建系统消息。

**属性**:
- `role_name`: 用户或助理角色的名称。
- `role_type`: 角色的类型，可以是 `RoleType.ASSISTANT` 或 `RoleType.USER` 等枚举值。
- `meta_dict`: 附加的元数据字典，用于存储消息的额外信息。
- `role`: 消息在 OpenAI 聊天系统中的角色，默认为 `"system"`。
- `content`: 消息的内容，默认为空字符串。

**代码描述**:
SystemMessage 类继承自 BaseMessage 类，专门用于生成和管理 CAMEL 聊天系统中的系统消息。该类通过定义如角色名称（`role_name`）、角色类型（`role_type`）、元数据字典（`meta_dict`）、角色（`role`）和内容（`content`）等属性，提供了一种结构化的方式来创建系统消息。其中，`role_type` 属性使用了 RoleType 枚举类，该枚举类定义了系统中可能的角色类型，如助理（`ASSISTANT`）和用户（`USER`）等。`meta_dict` 属性允许开发者为消息附加额外的元数据，这些元数据可以在消息处理过程中被利用。默认情况下，`role` 属性被设置为 `"system"`，表示这是一个系统消息，而 `content` 属性则用于存储消息的具体内容。

SystemMessage 类在项目中被多个不同的代理（Agent）和消息生成器（Generator）调用，以生成特定场景下的系统消息。例如，在 `ChatAgent` 类的初始化方法中，`system_message` 参数接受一个 SystemMessage 实例，用于定义聊天代理的系统消息。此外，`SystemMessageGenerator` 类的 `from_dict` 方法可以根据提供的元数据字典和角色元组生成定制的系统消息。

**注意**:
- 在使用 SystemMessage 类时，开发者需要确保正确设置 `role_name` 和 `role_type` 属性，因为这些属性决定了消息的角色身份和类型。
- 虽然 `content` 属性默认为空字符串，但在实际应用中，开发者应根据需要为其提供具体的消息内容，以确保消息的有效性和可理解性。
- `meta_dict` 属性提供了一种灵活的方式来附加额外信息，开发者应根据具体场景合理利用该属性。
## ClassDef AssistantSystemMessage
**AssistantSystemMessage**: AssistantSystemMessage 类用于创建来自助理的系统消息，这些消息在 CAMEL 聊天系统中使用。

**属性**:
- `role_name`: 表示助理角色的名称。
- `role_type`: 角色的类型，此处固定为 `RoleType.ASSISTANT`，表示消息来源于系统助理。
- `meta_dict`: 一个可选的字典，用于存储消息的额外元数据信息。
- `role`: 消息在 OpenAI 聊天系统中的角色，默认为 `"system"`，表示这是一个系统消息。
- `content`: 消息的具体内容，默认为空字符串。

**代码描述**:
AssistantSystemMessage 类继承自 SystemMessage 类，专门用于生成和管理来自系统助理的消息。通过定义 `role_name`、`role_type`、`meta_dict`、`role` 和 `content` 等属性，AssistantSystemMessage 提供了一种结构化的方式来创建助理的系统消息。`role_type` 属性在此类中被固定设置为 `RoleType.ASSISTANT`，明确指出消息发送者为系统助理，这有助于在处理消息时区分消息的来源。`meta_dict` 属性允许开发者为消息附加额外的元数据，这些元数据可以在消息处理过程中被利用。默认情况下，`role` 属性被设置为 `"system"`，强调了这是一个系统级别的消息，而 `content` 属性则用于存储消息的具体内容。

AssistantSystemMessage 类在 CAMEL 聊天系统中的应用场景包括但不限于系统提示、状态更新、帮助信息等，它通过提供一致的消息格式和类型，帮助系统更有效地与用户进行交互。

**注意**:
- 开发者在使用 AssistantSystemMessage 类时，应注意 `role_name` 属性需要根据实际助理角色的名称进行设置，以确保消息的准确性。
- 尽管 `content` 属性默认为空，但在实际使用中，开发者应根据需要提供具体的消息内容，以确保消息的有效传达。
- `meta_dict` 属性提供了一种灵活的方式来附加额外信息，开发者应根据具体场景合理利用该属性，以增强消息的信息量和实用性。
## ClassDef UserSystemMessage
**UserSystemMessage**: UserSystemMessage 类用于在 CAMEL 聊天系统中创建来自用户的系统消息。

**属性**:
- `role_name`: 用户角色的名称。
- `role_type`: 角色的类型，固定为 `RoleType.USER`。
- `meta_dict`: 附加的元数据字典，可用于存储消息的额外信息。
- `role`: 消息在 OpenAI 聊天系统中的角色，默认为 `"system"`。
- `content`: 消息的内容，默认为空字符串。

**代码描述**:
UserSystemMessage 类继承自 SystemMessage 类，专门用于生成和管理来自用户的系统消息。该类通过继承 SystemMessage 类的属性和方法，并设置 `role_type` 为 `RoleType.USER`，明确了其生成的系统消息是用户角色相关的。`role_name` 属性用于指定用户角色的名称，而 `meta_dict` 属性提供了一种灵活的方式来附加额外的信息，这些信息可以在消息处理过程中被利用。默认情况下，`role` 属性被设置为 `"system"`，表明这是一个系统消息，`content` 属性则用于存储消息的具体内容。

在 CAMEL 聊天系统中，UserSystemMessage 类可用于生成表示用户操作或状态的系统消息，例如用户加入聊天室或用户设置更改等事件。这些消息可以被系统的其他部分，如消息处理器或用户界面，用来提供反馈或更新状态。

**注意**:
- 在使用 UserSystemMessage 类时，开发者需要确保 `role_name` 属性正确反映了用户的角色名称，以保证消息的准确性。
- 虽然 `content` 属性默认为空，但在实际应用中，开发者应根据需要为其提供具体的消息内容，以确保消息的有效性和可理解性。
- `meta_dict` 属性提供了一种附加额外信息的灵活方式，开发者应根据具体场景合理利用该属性，以增强消息的信息量和实用性。
