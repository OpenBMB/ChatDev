# Ruby Sharp Edges

## Dynamic Code Execution

```ruby
# DANGEROUS: eval executes arbitrary code
eval(user_input)

# DANGEROUS: send calls arbitrary method
object.send(user_input, *args)
object.public_send(user_input)  # Only public, still dangerous

# DANGEROUS: constantize gets arbitrary class
user_input.constantize  # Rails
Object.const_get(user_input)

# DANGEROUS: instance_variable_get/set
obj.instance_variable_set("@#{user_input}", value)
```

**Real Vulnerabilities**:
- CVE-2013-0156: Rails XML parameter parsing led to code execution
- Countless Rails apps vulnerable to controller#action injection

**Fix**: Whitelist allowed values:
```ruby
ALLOWED_METHODS = %w[create update delete].freeze
raise unless ALLOWED_METHODS.include?(user_input)
object.send(user_input)
```

## YAML.load RCE

```ruby
# DANGEROUS: Like pickle, instantiates arbitrary objects
YAML.load(user_input)

# Attacker payload:
# --- !ruby/object:Gem::Installer
# i: x
# --- !ruby/object:Gem::SpecFetcher
# i: y
# --- !ruby/object:Gem::Requirement
# requirements:
#   !ruby/object:Gem::Package::TarReader
#   io: &1 !ruby/object:Net::BufferedIO
#     ...

# Chains through multiple classes to achieve RCE
```

**Fix**: Use `YAML.safe_load`:
```ruby
YAML.safe_load(user_input)
YAML.safe_load(user_input, permitted_classes: [Date, Time])
```

## Mass Assignment

```ruby
# DANGEROUS: All params assigned to model (Rails < 4)
User.new(params[:user])
# If params includes {admin: true, role: "superuser"}...

# Also dangerous with update_attributes
user.update_attributes(params[:user])
```

**Fix**: Strong Parameters (Rails 4+):
```ruby
def user_params
    params.require(:user).permit(:name, :email)  # Allowlist
end

User.new(user_params)
```

## SQL Injection

```ruby
# DANGEROUS: String interpolation in queries
User.where("name = '#{params[:name]}'")
User.where("name = '" + params[:name] + "'")

# DANGEROUS: Array form with interpolation
User.where(["name = ?", params[:name]])  # Safe
User.where(["name = #{params[:name]}"])  # NOT safe!

# DANGEROUS: order() with user input
User.order(params[:sort])  # Can inject: "name; DROP TABLE users--"
```

**Fix**: Use parameterized queries:
```ruby
User.where(name: params[:name])
User.where("name = ?", params[:name])
User.order(Arel.sql(sanitize(params[:sort])))  # With validation
```

## Command Injection

```ruby
# DANGEROUS: Backticks and system with interpolation
`ls #{params[:dir]}`
system("ls #{params[:dir]}")
exec("ls #{params[:dir]}")
%x(ls #{params[:dir]})

# Attacker: dir="; rm -rf /"
```

**Fix**: Use array form:
```ruby
system("ls", params[:dir])  # Argument passed safely
Open3.capture3("ls", params[:dir])
```

## Regex Injection

```ruby
# DANGEROUS: User input in regex
pattern = Regexp.new(params[:pattern])
string.match(pattern)

# ReDoS attack: pattern = "(a+)+"
# Denial of service

# Also: Anchors don't work as expected
/^admin$/.match("admin\nuser")  # Matches! ^ and $ match line boundaries
```

**Fix**: Use `\A` and `\z` for string boundaries:
```ruby
/\Aadmin\z/  # Only matches exactly "admin"
Regexp.escape(user_input)  # Escape special characters
```

## Symbol DoS (Ruby < 2.2)

```ruby
# DANGEROUS in Ruby < 2.2: Symbols never garbage collected
params[:key].to_sym  # Each unique key creates permanent symbol

# Attacker sends millions of unique parameter names
# Memory exhaustion - symbols fill memory
```

**Note**: Fixed in Ruby 2.2+ with symbol GC, but still worth avoiding unnecessary `to_sym` on user input.

## Method Visibility

```ruby
# DANGEROUS: private/protected don't prevent send()
class Secret
    private
    def sensitive_data
        "secret"
    end
end

obj.send(:sensitive_data)  # Works!
obj.sensitive_data         # NoMethodError (as expected)
```

## Default Mutable Arguments

```ruby
# DANGEROUS: Same pattern as Python
def add_item(item, list = [])
    list << item
    list
end

add_item(1)  # [1]
add_item(2)  # [1, 2] - same array!
```

**Fix**: Use nil default:
```ruby
def add_item(item, list = nil)
    list ||= []
    list << item
end
```

## ERB Template Injection

```ruby
# DANGEROUS: User input in ERB template
template = ERB.new(params[:template])
template.result(binding)

# Attacker template: <%= `whoami` %>
# Executes shell command

# Also via:
template = params[:template]
eval("\"#{template}\"")  # If template contains #{}
```

## File Operations

```ruby
# DANGEROUS: Path traversal
File.read("uploads/#{params[:filename]}")
# Attacker: filename=../../../etc/passwd

# DANGEROUS: File.open with pipe
File.open("|#{params[:cmd]}")  # Executes command!

# The | prefix runs a command and opens pipe to it
File.read("|whoami")  # Returns output of whoami
```

**Fix**: Validate and sanitize paths:
```ruby
path = File.expand_path(params[:filename], uploads_dir)
raise unless path.start_with?(uploads_dir)
```

## Comparison Gotchas

```ruby
# DANGEROUS: == vs eql? vs equal?
a = "hello"
b = "hello"

a == b       # true - value comparison
a.eql?(b)    # true - value + type comparison
a.equal?(b)  # false - identity comparison

# Array comparison
[1, 2] == [1, 2]  # true
[1, 2].eql?([1, 2])  # true
[1, 2].equal?([1, 2])  # false
```

## Thread Safety

```ruby
# DANGEROUS: Ruby global interpreter lock (GIL) doesn't protect everything
@counter = 0

threads = 10.times.map do
    Thread.new { 1000.times { @counter += 1 } }
end
threads.each(&:join)

@counter  # May not be 10000! Read-modify-write isn't atomic
```

**Fix**: Use Mutex or atomic operations:
```ruby
mutex = Mutex.new
mutex.synchronize { @counter += 1 }
```

## Detection Patterns

| Pattern | Risk |
|---------|------|
| `eval(`, `instance_eval(` | Code execution |
| `.send(user_input`, `.public_send(` | Method injection |
| `.constantize`, `const_get(` | Class injection |
| `YAML.load(` | Deserialization RCE |
| `.new(params[` without strong params | Mass assignment |
| `where("... #{` | SQL injection |
| `` `...#{` ``, `system("...#{` | Command injection |
| `Regexp.new(user_input)` | ReDoS |
| `params[:x].to_sym` | Symbol DoS (old Ruby) |
| `ERB.new(user_input)` | Template injection |
| `File.read("|...` or `File.open("|...` | Command execution |
| `File.read(params[` without path validation | Path traversal |
