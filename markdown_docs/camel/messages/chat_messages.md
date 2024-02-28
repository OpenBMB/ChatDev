## ClassDef ChatMessage
**ChatMessage**: ChatMessage 类是用于 CAMEL 聊天系统中的聊天消息的基类。

**属性**:
- `role_name`: 用户或助理角色的名称。
- `role_type`: 角色的类型，可以是 `RoleType.ASSISTANT` 或 `RoleType.USER`。
- `meta_dict`: 附加的元数据字典，用于消息。
- `role`: 消息在 OpenAI 聊天系统中的角色。
- `content`: 消息的内容，默认为空字符串。
- `function_call`: 当使用新的 OpenAI API 时，此属性用于存储函数调用。
- `tool_calls`: 当使用新的 OpenAI API 时，此属性用于存储工具调用。

**代码描述**:
ChatMessage 类继承自 BaseMessage 类，提供了一个用于 CAMEL 聊天系统中处理聊天消息的基础框架。它定义了消息的基本属性，如角色名称、角色类型、元数据、角色和内容。此外，如果启用了新的 OpenAI API，它还支持存储函数调用和工具调用的信息。

ChatMessage 类的一个关键方法是 `set_user_role_at_backend`，该方法允许在后端设置用户角色。这个方法通过创建一个新的 ChatMessage 实例并将角色设置为 "user" 来实现，同时保留其他属性不变。这对于在聊天系统中处理角色转换非常有用。

**注意**:
- 在使用 ChatMessage 类时，开发者需要确保正确设置消息的角色和类型，因为这会影响消息的处理和表示。
- ChatMessage 类设计为可扩展的基类，开发者可以根据需要创建派生类，以支持更复杂的消息类型和操作。

**输出示例**:
```python
message = ChatMessage(role_name="user", role_type=RoleType.USER, meta_dict={"key": "value"}, role="user", content="Hello, world!")
print(message.to_dict())
```
可能的输出为:
```python
{
    "role_name": "user",
    "role_type": "USER",
    "key": "value",
    "role": "user",
    "content": "Hello, world!"
}
```

在项目中，ChatMessage 类被广泛用于处理和表示聊天系统中的消息。它不仅在聊天代理（ChatAgent）和批评代理（CriticAgent）中用于生成和处理消息，还在角色扮演（RolePlaying）和人类交互（Human）场景中发挥作用，以支持复杂的聊天逻辑和用户交互。此外，ChatMessage 类的灵活性和扩展性使其成为构建和维护 CAMEL 聊天系统的重要基础。
### FunctionDef set_user_role_at_backend(self)
**set_user_role_at_backend**: 此函数的功能是创建一个新的消息实例，将消息的角色设置为"user"。

**参数**:
- `self`: 表示BaseMessage类的一个实例，即当前消息对象。

**代码描述**:
`set_user_role_at_backend`函数是`ChatMessage`类的一个方法，用于在后端设置用户角色。此函数通过调用`__class__`方法创建当前消息对象的一个新实例，同时保留原有的角色名称(`role_name`)、角色类型(`role_type`)、元数据字典(`meta_dict`)和内容(`content`)，但将角色(`role`)强制设置为"user"。这意味着无论原消息的角色是什么，通过此函数创建的新消息实例的角色都将是"user"。

此方法利用了`BaseMessage`类的能力来创建一个内容相同但角色不同的新消息实例。这在需要根据不同的用户角色处理消息时非常有用，例如，在角色扮演或多用户聊天系统中切换用户角色。

**注意**:
- 使用此函数时，需要确保`ChatMessage`类继承自`BaseMessage`类，因为它依赖于`BaseMessage`类的属性和方法。
- 此函数不修改原消息实例，而是返回一个新的实例，因此需要适当处理返回的新消息实例。

**输出示例**:
假设有一个消息实例`msg`，其角色原本为"assistant"，通过调用`msg.set_user_role_at_backend()`后，将得到一个新的消息实例，其内容与`msg`相同，但角色为"user"。如果原消息内容为"Hello, world!"，则新消息实例的内容也为"Hello, world!"，但角色为"user"。

在项目中，`set_user_role_at_backend`函数被用于在不同阶段的消息处理中，确保消息以正确的用户角色进行处理。例如，在`CriticAgent`的`step`方法和`RolePlaying`的`step`方法中，都调用了此函数来确保消息以"user"角色进行后续处理，这对于实现系统中的角色管理和消息流转控制至关重要。
***
## ClassDef AssistantChatMessage
**AssistantChatMessage**: AssistantChatMessage 类用于表示 CAMEL 聊天系统中助理角色发送的聊天消息。

**属性**:
- `role_name`: 助理角色的名称。
- `role_type`: 角色的类型，固定为 `RoleType.ASSISTANT`。
- `meta_dict`: 附加的元数据字典，可用于存储消息相关的额外信息。
- `role`: 消息在 OpenAI 聊天系统中的角色，默认为 `"user"`，这里可能是代码中的一个错误，应该是 `"assistant"`。
- `content`: 消息的内容，默认为空字符串。

**代码描述**:
AssistantChatMessage 类继承自 ChatMessage 类，专门用于处理 CAMEL 聊天系统中助理角色发送的消息。该类通过预设 `role_type` 为 `RoleType.ASSISTANT` 来明确标识消息发送者的角色类型为助理。此外，它还允许通过 `meta_dict` 属性为消息附加额外的元数据信息，从而提供更多上下文或辅助信息。

在初始化时，`role` 属性被默认设置为 `"user"`，这可能是一个错误，因为从类的用途来看，`role` 应该被设置为 `"assistant"`。这一点需要在实际使用时注意校正。`content` 属性用于存储消息的具体内容，初始化为空字符串，允许在创建实例时通过参数传入具体的消息内容。

**注意**:
- 在使用 AssistantChatMessage 类时，开发者应注意 `role` 属性的默认值可能不正确，正确的值应为 `"assistant"`。如果在代码中直接使用该类，可能需要手动设置 `role` 属性以确保消息角色的准确性。
- 由于 `role_type` 被固定设置为 `RoleType.ASSISTANT`，这个类专门用于助理角色的消息，不适用于用户或其他角色的消息。
- `meta_dict` 属性提供了一种灵活的方式来附加额外的信息到消息中，开发者可以根据需要利用这一特性来传递更多的上下文信息。
## ClassDef UserChatMessage
**UserChatMessage**: UserChatMessage 类用于表示 CAMEL 聊天系统中用户角色发出的聊天消息。

**属性**:
- `role_name`: 用户角色的名称。
- `role_type`: 用户角色的类型，固定为 `RoleType.USER`。
- `meta_dict`: 附加的元数据字典，可用于存储消息相关的额外信息。
- `role`: 消息在 OpenAI 聊天系统中的角色，此处默认为 `"user"`。
- `content`: 聊天消息的内容，默认为空字符串。

**代码描述**:
UserChatMessage 类继承自 ChatMessage 类，专门用于处理用户角色发出的聊天消息。通过定义 `role_type` 为 `RoleType.USER`，明确指出该消息来源于用户。此外，类中还包含了 `meta_dict` 字典，允许开发者为消息附加额外的元数据，增强消息的表达能力和灵活性。

在实际应用中，UserChatMessage 类的实例可能会在不同的场景下被创建和使用。例如，在角色扮演（RolePlaying）的初始化聊天过程中，通过 UserChatMessage 来模拟用户消息，启动聊天流程。同样，在任务指定（TaskSpecifyAgent）和任务规划（TaskPlannerAgent）的步骤中，也会创建 UserChatMessage 实例，以模拟用户对特定任务的描述或请求，进而触发相应的处理逻辑。

**注意**:
- 在使用 UserChatMessage 类时，开发者应确保 `role_name` 和 `content` 属性被正确设置，以反映消息的实际内容和来源。
- 虽然 `meta_dict` 是可选的，但在需要传递额外信息时，合理利用此属性可以提升消息处理的灵活性和效率。
- 由于 UserChatMessage 类固定了 `role_type` 为 `RoleType.USER`，因此在需要表示其他角色类型的消息时，应考虑使用 ChatMessage 类或其它更适合的派生类。
