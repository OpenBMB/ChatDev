## FunctionDef return_prompt_wrapper(cls, func)
**return_prompt_wrapper**: 此函数的功能是将被装饰函数的返回值，如果是字符串，则转换为输入类的实例。

**参数**:
- `cls` (type): 需要转换成的类。
- `func` (Callable): 被装饰的函数。

**代码描述**:
`return_prompt_wrapper` 是一个装饰器函数，旨在处理另一个函数的返回值。当被装饰的函数返回一个字符串时，此装饰器会将该字符串转换为`cls`参数指定的类的实例。如果返回值是一个元组，装饰器会遍历元组中的每个元素，将其中的字符串元素转换为`cls`类的实例，其他类型的元素保持不变。如果返回值既不是字符串也不是元组，或者已经是`cls`的实例，则直接返回原值。

此函数在项目中被`wrap_prompt_functions`函数调用，用于自动装饰一个类中的所有适合的函数。这样，任何返回字符串的函数都会自动将其返回值转换为特定的类实例，这对于创建和处理文本提示类特别有用。

**注意**:
- 被装饰的函数的原始属性（如`__name__`和`__doc__`）会被保留，这意味着装饰后的函数对外表现得就像原始函数一样，不会因为装饰操作而丢失文档字符串或其他元数据。
- 此装饰器假设`cls`类可以接受一个字符串作为其构造函数的参数来创建实例。如果`cls`的构造函数不接受字符串参数，使用此装饰器可能会导致错误。

**输出示例**:
假设有一个类`TextPrompt`，其构造函数接受一个字符串参数。如果有一个函数`generate_prompt`返回一个字符串`"Hello, world!"`，使用`return_prompt_wrapper(TextPrompt, generate_prompt)`装饰后，调用`generate_prompt()`将返回一个`TextPrompt`实例，而不是原始的字符串。如果`generate_prompt`返回的是一个包含字符串的元组，如`("Hello, world!", "Goodbye, world!")`，则每个字符串元素都会被转换为`TextPrompt`实例。
### FunctionDef wrapper
**wrapper**: wrapper函数的功能是将传入的参数转换为`TextPrompt`实例或者保持原样返回。

**参数**:
- *args (Any): 可变长度的位置参数列表。
- **kwargs (Any): 任意的关键字参数。

**代码描述**:
wrapper函数接受任意数量的位置参数和关键字参数。它的主要作用是对传入的参数进行处理，将其转换为`TextPrompt`实例，或者在特定条件下保持原样返回。具体行为如下：
1. 首先，函数尝试调用`func`（未在代码段中定义，可能是外部传入的函数）并传入所有接收到的参数。
2. 如果`func`的返回值是一个字符串，并且这个字符串不是`cls`（未在代码段中明确指出，可能是`TextPrompt`的类引用）的实例，那么这个字符串将被转换为`cls`的实例后返回。
3. 如果`func`的返回值是一个元组，那么会遍历这个元组中的每一个元素。对于元组中的每个字符串元素，如果它不是`cls`的实例，同样会被转换为`cls`的实例。最终返回一个新的元组，其中包含了转换后的元素以及原始不需要转换的元素。
4. 如果`func`的返回值既不是字符串也不是元组，或者不满足转换条件，那么这个返回值将直接被返回。

**注意**:
- 在使用wrapper函数时，需要确保传入的`func`函数以及`cls`类已经正确定义，且`cls`类能够接受字符串作为参数来创建实例。
- 由于代码中没有明确展示`func`和`cls`的定义，使用此函数前需要确保这两个关键组件的正确实现。

**输出示例**:
假设`cls`为`TextPrompt`类，且`func`函数返回值为`"example string"`，则调用`wrapper`函数可能的返回值为`TextPrompt("example string")`。如果`func`返回值为`("example string", "another string")`，且这些字符串不是`TextPrompt`的实例，则返回值可能为`(TextPrompt("example string"), TextPrompt("another string"))`。
***
## FunctionDef wrap_prompt_functions(cls)
**wrap_prompt_functions**: 此函数的功能是自动装饰一个继承自字符串类的类中的所有函数，使这些函数的返回值可以通过`return_prompt_wrapper`装饰器转换为特定类的实例。

**参数**:
- `cls` (type): 需要装饰的类。

**代码描述**: `wrap_prompt_functions`是一个装饰器工厂，它接收一个类作为参数。此函数首先定义了一个排除属性集合，包括`__init__`, `__new__`, `__str__`, 和 `__repr__`，这些方法不会被装饰。接着，它遍历类的所有属性，对于每一个可调用的属性（即方法），如果该属性不在排除集合中，并且是一个常规方法（使用`inspect.isroutine`判断），则使用`return_prompt_wrapper`装饰器来装饰这个方法。`return_prompt_wrapper`装饰器的作用是将方法的返回值，如果是字符串，则转换为输入类的实例。这样，被装饰的类中的所有适合的方法都会自动将其字符串返回值转换为特定的类实例，这对于创建和处理文本提示类特别有用。

**注意**:
- 被装饰的方法应该是那些原本返回字符串的方法，因为`return_prompt_wrapper`装饰器会将字符串返回值转换为类实例。
- 如果类的构造函数不接受字符串作为参数，使用此装饰器可能会导致错误，因为`return_prompt_wrapper`假设目标类可以使用一个字符串来创建实例。

**输出示例**: 假设有一个类`TextPrompt`，其构造函数接受一个字符串参数。如果类`Example`中有一个方法`generate_prompt`原本返回一个字符串`"Hello, world!"`，在`Example`类上应用`wrap_prompt_functions`装饰器后，调用`Example().generate_prompt()`将返回一个`TextPrompt`实例，而不是原始的字符串。这表明`wrap_prompt_functions`成功地将`Example`类中所有合适的方法的返回值自动转换为了`TextPrompt`实例。
## ClassDef TextPrompt
**TextPrompt**: TextPrompt类是对字符串进行扩展，用于表示文本提示，并提供获取提示中关键词集合的属性。

**属性**:
- key_words: 表示在提示中的关键词集合的一个集合。

**代码描述**:
TextPrompt类继承自Python内置的str类，主要用于表示文本提示。它通过扩展str类，增加了一些特定的功能，使其更适合在文本提示处理中使用。TextPrompt类提供了两个主要的功能：
1. 获取提示中的关键词集合：通过key_words属性，可以获取到文本提示中所有关键词的集合。这是通过调用camel.utils模块中的get_prompt_template_key_words函数实现的，该函数负责解析文本提示并提取其中的关键词。
2. 格式化文本提示：TextPrompt类重写了str类的format方法，允许在格式化字符串时使用默认值。这使得在只有部分字符串需要格式化时，也能够方便地进行操作。在格式化过程中，首先会为每个关键词生成一个默认的格式化字符串，然后使用用户提供的参数进行更新，最后返回一个新的TextPrompt对象，其中的格式化字符串已被替换为格式化后的字符串。

在项目中，TextPrompt类被多个对象调用，例如TaskSpecifyAgent和TaskPlannerAgent等，它们使用TextPrompt来生成或修改任务说明文本。这些应用场景表明TextPrompt类在处理文本提示、生成任务说明等方面发挥了重要作用。

**注意**:
- TextPrompt类在使用时，需要注意其继承自str类，因此它可以使用str类的所有方法和属性。但是，当需要使用TextPrompt特有的功能，如key_words属性或重写的format方法时，应确保操作的对象是TextPrompt实例。
- 在使用format方法进行文本格式化时，应注意正确地传递参数，尤其是在处理关键词和默认值时，以确保生成的文本提示符合预期。

**输出示例**:
假设有一个TextPrompt实例，其内容为"请根据{task}完成任务"，其中"{task}"是一个关键词。调用key_words属性将返回一个集合{"task"}。如果调用format方法并传递参数task="编写文档"，则返回的新TextPrompt对象将是"请根据编写文档完成任务"。
### FunctionDef key_words(self)
**key_words**: 此函数的功能是返回一个代表提示中关键词的字符串集合。

**参数**: 此函数没有参数。

**代码描述**: `key_words` 方法是 `TextPrompt` 类的一个成员方法，它的主要作用是从提示文本中提取关键词。该方法首先从 `camel.utils` 模块导入 `get_prompt_template_key_words` 函数，然后调用这个函数，并将当前对象 `self` 作为参数传递。`get_prompt_template_key_words` 函数负责从包含大括号 `{}` 的字符串模板中提取出括号内的单词或短语，并以集合的形式返回这些关键词。因此，`key_words` 方法最终返回的是一个字符串集合，集合中的每个元素都是提示文本模板中的一个关键词。

**注意**:
- `key_words` 方法的返回值依赖于 `get_prompt_template_key_words` 函数的实现，特别是在处理大括号 `{}` 包裹的关键词提取方面。
- 在使用 `key_words` 方法时，需要确保 `TextPrompt` 对象的文本模板格式正确，即关键词或短语被大括号 `{}` 正确包裹。否则，可能无法正确提取关键词。

**输出示例**: 假设 `TextPrompt` 对象的文本模板为 `"欢迎您, {用户}! 您的账户状态为{状态}。"`，调用 `key_words` 方法将返回集合 `{'用户', '状态'}`。

在项目中，`key_words` 方法的一个重要应用场景是在 `camel/generators.py` 中的 `SystemMessageGenerator` 类的初始化过程中。在这个过程中，通过调用不同角色类型的提示模板的 `key_words` 方法，可以收集并合并所有相关提示模板中的关键词，从而构建出一个包含所有必要关键词的集合。这对于后续生成系统消息时，根据不同角色类型和任务需求动态填充提示模板提供了便利。

此外，`key_words` 方法还在 `TextPrompt` 类的 `format` 方法中被用到，用于在格式化提示文本时提供默认的关键词值，确保即使在某些关键词未被明确提供值的情况下，提示文本仍能保持一定的完整性和可读性。
***
### FunctionDef format(self)
**format**: `format` 函数的功能是允许在格式化字符串中使用默认值，用于格式化部分字符串。

**参数**:
- `*args (Any)`: 可变长度参数列表。
- `**kwargs (Any)`: 任意关键字参数。

**代码描述**: 此函数重写了内置的 `str.format` 方法，以允许在格式字符串中使用默认值。它首先创建一个包含所有关键词作为键，其对应格式化占位符作为值的字典 `default_kwargs`。这个字典随后被更新，以包含调用时传递的任意关键字参数 `kwargs`。最终，这个更新后的字典 `default_kwargs` 被用于替换格式字符串中的占位符。函数返回一个新的 `TextPrompt` 对象，该对象的格式字符串被替换为格式化后的字符串。

**注意**:
- 在使用 `format` 方法时，需要确保 `TextPrompt` 对象已经正确初始化，且其 `key_words` 方法能够返回正确的关键词集合。这是因为 `format` 方法在构建默认关键词值时依赖于 `key_words` 方法的返回结果。
- 此方法允许在格式化字符串时提供默认值，这有助于在某些关键词未被明确提供值的情况下，保持提示文本的完整性和可读性。

**输出示例**: 假设有一个 `TextPrompt` 对象，其文本模板为 `"Hello, {name}! Your account status is {status}."`，且该对象的 `key_words` 方法返回集合 `{'name', 'status'}`。如果调用 `format` 方法时没有提供任何参数，则返回的 `TextPrompt` 对象的文本模板将被替换为 `"Hello, {name}! Your account status is {status}."`，其中 `{name}` 和 `{status}` 保持不变，因为它们是默认值。如果调用时提供了 `name='Alice'`，则返回的文本模板将为 `"Hello, Alice! Your account status is {status}."`。
***
## ClassDef CodePrompt
**CodePrompt**: CodePrompt类是用于表示代码提示的类，它扩展了TextPrompt类，增加了对代码类型的支持。

**属性**:
- code_string: 用于存储代码字符串的属性。
- code_type: 代码的类型，例如Python、JavaScript等，是一个可选属性，默认为None。

**代码描述**:
CodePrompt类继承自TextPrompt类，专门用于处理代码相关的提示。它通过新增一个`code_type`属性来区分不同类型的代码，使得在处理代码时能够提供更加具体的上下文信息。在创建CodePrompt实例时，可以通过`code_type`关键字参数指定代码的类型。

该类重写了`__new__`方法，以确保在实例化时能够正确处理`code_type`参数，并将其存储在实例的私有属性`_code_type`中。此外，通过`code_type`属性的getter和setter方法，可以方便地获取和设置代码的类型。

CodePrompt类还提供了一个`execute`方法，用于执行存储在`code_string`中的代码字符串。该方法接受一个可选的`global_vars`字典参数，用于指定执行代码时的全局变量。`execute`方法会尝试执行代码，并捕获任何发生的异常，返回执行结果或异常的跟踪信息。这一功能主要支持Python代码的执行。

**注意**:
- CodePrompt类目前仅支持Python代码的执行。在未来可能会扩展支持更多编程语言。
- 在使用`execute`方法执行代码时，需要注意代码执行的安全性，避免执行不信任的代码。

**输出示例**:
假设有一个CodePrompt实例，其`code_string`为`"print('Hello, World!')"`，`code_type`为`"Python"`。调用`execute`方法时，如果代码执行成功，将返回一个元组，其中第一个元素为字符串`"Hello, World!\n"`，第二个元素为一个包含局部变量的字典（如果有的话）；如果执行过程中发生异常，则第一个元素为异常的跟踪信息字符串，第二个元素为None。

通过这种方式，CodePrompt类为处理和执行代码提供了一个灵活且强大的工具，特别适合于需要在应用程序中嵌入代码执行功能的场景。
### FunctionDef __new__(cls)
**__new__**: 该函数用于创建`CodePrompt`类的新实例。

**参数**:
- `*args` (Any): 位置参数。
- `**kwargs` (Any): 关键字参数。

**代码描述**:
`__new__`方法是一个特殊的方法，用于在一个对象实例化之前创建这个对象。在`CodePrompt`类中，`__new__`方法被用来创建`CodePrompt`类的新实例。此方法首先从`kwargs`中弹出`code_type`关键字参数（如果存在），默认值为`None`。然后，使用`super().__new__(cls, *args, **kwargs)`调用基类的`__new__`方法来实际创建实例。创建实例后，将`code_type`参数的值赋给实例的`_code_type`属性。最后，返回创建的实例。

**注意**:
- `__new__`方法通常用于控制对象的创建过程。在大多数情况下，类的实例化过程不需要显式地定义`__new__`方法，除非需要对实例化过程进行特殊的控制或者修改。
- 在使用`__new__`方法时，需要确保正确地调用基类的`__new__`方法，并且返回实例。
- `code_type`参数是可选的，用于提供创建`CodePrompt`实例时的额外信息，但不是创建实例所必需的。

**输出示例**:
这个方法不直接产生可视化的输出，而是返回一个`CodePrompt`类的实例。例如，如果调用`CodePrompt(code_type='Python')`，则此方法将返回一个`CodePrompt`实例，其中`_code_type`属性被设置为`'Python'`。
***
### FunctionDef code_type(self)
**code_type**: 此函数的功能是返回代码的类型。

**参数**: 此函数没有参数。

**函数描述**: `code_type` 函数是一个成员方法，用于获取代码的类型。它不接受任何参数，并返回一个字符串或者在没有设置代码类型时返回 None。这意味着该函数的返回值是可选的字符串（`Optional[str]`），这在类型提示中得到了体现。如果代码类型已经被设置，则此函数返回相应的字符串值；如果未设置，则返回 None。这个功能对于在处理不同类型的代码时，需要根据代码类型采取不同操作的场景非常有用。

**注意**: 使用此函数时，需要确保`_code_type`属性已经在对象初始化或者在某个时间点被正确设置，否则它将返回 None。这意味着在调用此函数之前，应该有一个明确的代码类型设置流程。

**输出示例**: 假设`_code_type`属性被设置为 `"Python"`，那么调用`code_type`函数将返回：
```
"Python"
```
如果`_code_type`属性未被设置，调用此函数将返回：
```
None
```
***
### FunctionDef set_code_type(self, code_type)
**set_code_type**: 此函数用于设置代码的类型。

**参数**:
- code_type (str): 代码的类型。

**代码描述**:
`set_code_type` 函数是一个成员函数，它允许用户为某个实例设置代码类型。这个函数接受一个参数 `code_type`，这是一个字符串，表示代码的类型。函数内部通过将 `code_type` 参数的值赋给实例的私有成员变量 `_code_type` 来实现设置代码类型的功能。这意味着，一旦调用此函数并传入相应的代码类型，该实例的代码类型就会被更新为传入的值。

**注意**:
- 在使用此函数时，需要确保传入的 `code_type` 参数是一个有效的字符串，且符合预期的代码类型格式。不正确的代码类型可能会导致后续操作出现问题。
- 该函数不返回任何值，仅用于设置实例的代码类型。
***
### FunctionDef execute(self, global_vars)
**execute**: 此函数的功能是执行代码字符串，并捕获错误或返回输出字符串和局部变量。

**参数**:
- `global_vars` (Dict, 可选): 在代码执行期间使用的全局变量。默认值为`None`。

**代码描述**:
`execute`函数主要用于执行代码字符串。它接受一个可选的字典参数`global_vars`，该参数用于定义代码执行时的全局变量环境。如果未提供`global_vars`，则默认使用Python的`globals()`，即当前全局变量环境。

函数执行流程如下：
1. 首先，使用`io.StringIO`创建一个字符串IO流，用于捕获代码执行的输出。
2. 将`sys.stdout`重定向到上一步创建的字符串IO流，这样代码执行的所有输出都会被捕获。
3. 使用`exec`函数执行代码字符串。`exec`接受三个参数：要执行的代码字符串、全局变量字典和局部变量字典。在本函数中，代码字符串由`self`表示，局部变量字典初始化为空字典。
4. 执行完毕后，将`sys.stdout`重置为原始的标准输出。
5. 读取并返回字符串IO流中的内容，即代码执行的输出，以及局部变量字典。

如果在执行过程中发生异常，函数会捕获异常并使用`traceback.format_exc`获取异常的堆栈跟踪字符串。然后，重置`sys.stdout`为原始标准输出，并返回异常的堆栈跟踪字符串和`None`（表示没有局部变量返回）。

**注意**:
- 当前版本的`execute`函数仅支持执行Python代码。
- 在使用此函数时，需要注意代码执行的安全性，尤其是当执行未知或不受信任的代码字符串时。

**输出示例**:
假设执行的代码字符串为`print("Hello, World!")`，没有发生错误，那么函数的返回值可能如下：
```
("Hello, World!\n", {})
```
这表示输出字符串为`"Hello, World!\n"`，并且没有局部变量返回。

如果执行的代码字符串导致了异常，例如尝试执行`1/0`，那么函数的返回值可能如下：
```
("Traceback (most recent call last):\n  File \"<string>\", line 1, in <module>\nZeroDivisionError: division by zero\n", None)
```
这表示捕获到了一个除以零的异常，并返回了相应的堆栈跟踪信息。
***
## ClassDef TextPromptDict
**TextPromptDict**: TextPromptDict类的功能是实现一个从键映射到TextPrompt对象的字典。

**属性**:
- EMBODIMENT_PROMPT: 一个TextPrompt实例，定义了一个具体的文本提示模板，用于描述“身体化”的角色在执行任务时应遵循的指导原则和动作空间。

**代码描述**:
TextPromptDict类继承自Python的字典类型（Dict），专门用于存储和管理键与TextPrompt对象之间的映射关系。这个类通过定义一个特定的TextPrompt实例（EMBODIMENT_PROMPT），提供了一个具体的文本提示模板。这个模板用于指导如何以一种“身体化”的角色来执行任务，包括但不限于在物理世界中浏览互联网、阅读文档、绘制图像、创建视频、执行代码等活动。

在TextPromptDict的构造函数中，通过调用父类的构造函数初始化字典，并使用update方法添加一个特定的键（RoleType.EMBODIMENT）与EMBODIMENT_PROMPT实例的映射。这样，当需要根据角色类型获取相应的文本提示时，可以直接从这个字典中查找。

**注意**:
- TextPromptDict类在使用时，需要注意它是基于Python的字典类型实现的，因此可以使用所有字典类型的方法和属性。但是，它特别用于存储键与TextPrompt对象之间的映射关系，因此在添加或修改映射时，应确保键的类型和值的类型符合预期。
- EMBODIMENT_PROMPT定义的文本提示模板中包含了多个占位符（如{role}、{task}、{action_space}），这些占位符在使用时需要根据具体的任务和角色类型进行替换，以生成具体的指导文本。
- 由于TextPrompt类重写了str类的format方法，支持在格式化字符串时使用默认值，因此在使用EMBODIMENT_PROMPT进行格式化时，可以灵活地处理缺少某些参数的情况，从而避免格式化错误。

TextPromptDict类在项目中的作用是提供一个统一的方式来管理和获取不同角色类型所需的文本提示，这对于实现角色特定的任务执行逻辑非常重要。通过预定义的文本提示模板，可以更加方便地指导“身体化”角色如何根据接收到的指令在物理世界中进行操作，从而提高任务执行的效率和准确性。
### FunctionDef __init__(self)
**__init__**: 此函数的功能是初始化 TextPromptDict 对象，并更新其内容。

**参数**:
- *args: 接受任意数量的位置参数。
- **kwargs: 接受任意数量的关键字参数。

**代码描述**: `__init__` 方法是 `TextPromptDict` 类的构造函数，用于初始化该类的实例。在这个方法中，首先通过 `super().__init__(*args, **kwargs)` 调用父类的构造函数，确保父类被正确初始化。接着，该方法使用 `update` 方法更新字典的内容，其中键为 `RoleType.EMBODIMENT`，值为 `self.EMBODIMENT_PROMPT`。这里 `RoleType.EMBODIMENT` 来自于 `RoleType` 枚举类，表示具体化角色类型，而 `self.EMBODIMENT_PROMPT` 是 `TextPromptDict` 类的一个属性，用于存储与具体化角色相关的提示信息。

`RoleType` 类在这里的使用表明 `TextPromptDict` 类与系统中角色类型的定义紧密相关。通过将 `RoleType.EMBODIMENT` 作为键，`TextPromptDict` 类能够针对不同的角色类型存储和管理相关的提示信息，这对于实现基于角色的动态提示生成逻辑至关重要。

**注意**:
- 在使用 `TextPromptDict` 类时，开发者应确保 `EMBODIMENT_PROMPT` 属性已被正确定义和初始化，否则在调用 `__init__` 方法时可能会遇到引用错误。
- `RoleType` 类提供的枚举值应与 `TextPromptDict` 类中使用的键保持一致，以确保角色类型与提示信息之间的正确映射。
***
