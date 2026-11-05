/**
 * @name [VARIANT_NAME]
 * @description Find variants of [ORIGINAL_BUG_ID]
 * @kind path-problem
 * @problem.severity error
 * @tags security variant-analysis
 */

import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import semmle.code.cpp.security.Security
import DataFlow::PathGraph

module VariantConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // Command line arguments
    exists(Parameter p |
      p.getName() = "argv" and
      source.asParameter() = p
    )
    or
    // Standard input
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["gets", "fgets", "scanf", "fscanf", "sscanf", "getline", "getchar", "fgetc"] and
      source.asExpr() = fc
    )
    or
    // Network input
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["recv", "recvfrom", "recvmsg", "read"] and
      source.asExpr() = fc
    )
    or
    // Environment variables
    exists(FunctionCall fc |
      fc.getTarget().getName() = "getenv" and
      source.asExpr() = fc
    )
    or
    // File input
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["fread", "fgets"] and
      source.asExpr() = fc.getArgument(0)
    )
  }

  predicate isSink(DataFlow::Node sink) {
    // Command injection
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["system", "popen", "execl", "execlp", "execle", "execv", "execvp", "execvpe"] and
      sink.asExpr() = fc.getArgument(0)
    )
    or
    // Buffer overflow (unsafe string functions)
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["strcpy", "strcat", "sprintf", "vsprintf", "gets"] and
      sink.asExpr() = fc.getArgument(1)
    )
    or
    // Format string
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["printf", "fprintf", "sprintf", "snprintf", "syslog"] and
      sink.asExpr() = fc.getArgument(0)
    )
    or
    // Memory allocation (integer overflow)
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["malloc", "calloc", "realloc", "alloca"] and
      sink.asExpr() = fc.getArgument(0)
    )
    or
    // Path traversal
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["fopen", "open", "access", "stat", "lstat"] and
      sink.asExpr() = fc.getArgument(0)
    )
    or
    // SQL (if using embedded SQL or libraries)
    exists(FunctionCall fc |
      fc.getTarget().getName().matches("%query%") and
      sink.asExpr() = fc.getAnArgument()
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    // Input validation
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["strlen", "strnlen", "isalpha", "isdigit", "isalnum"] and
      node.asExpr() = fc
    )
    or
    // Safe string functions (size-bounded)
    exists(FunctionCall fc |
      fc.getTarget().getName() in ["strncpy", "strncat", "snprintf"] and
      node.asExpr() = fc
    )
    or
    // Sanitization
    exists(FunctionCall fc |
      fc.getTarget().getName().matches("%escape%") and
      node.asExpr() = fc
    )
    or
    // Integer bounds check
    exists(IfStmt check, RelationalOperation cmp |
      cmp = check.getCondition() and
      node.asExpr() = cmp.getAnOperand()
    )
  }
}

module VariantFlow = TaintTracking::Global<VariantConfig>;
import VariantFlow::PathGraph

from VariantFlow::PathNode source, VariantFlow::PathNode sink
where VariantFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Tainted data from $@ flows to dangerous sink.",
  source.getNode(), "user input"
