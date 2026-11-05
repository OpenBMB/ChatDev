/**
 * @name [VARIANT_NAME]
 * @description Find variants of [ORIGINAL_BUG_ID]
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @tags security
 *       variant-analysis
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.ApiGraphs

module VariantConfig implements DataFlow::ConfigSig {
  // Sources: where untrusted data originates
  predicate isSource(DataFlow::Node source) {
    // Flask request parameters
    source = API::moduleImport("flask").getMember("request")
             .getMember(["args", "form", "json", "data"])
             .getAUse()
    or
    // Environment variables
    exists(Call c |
      c.getFunc().(Attribute).getObject().(Name).getId() = "os" and
      c.getFunc().(Attribute).getName() in ["getenv", "environ"] and
      source.asExpr() = c
    )
  }

  // Sinks: where tainted data becomes dangerous
  predicate isSink(DataFlow::Node sink) {
    // os.system()
    exists(Call c |
      c.getFunc().(Attribute).getObject().(Name).getId() = "os" and
      c.getFunc().(Attribute).getName() = "system" and
      sink.asExpr() = c.getArg(0)
    )
    or
    // subprocess with shell=True
    exists(Call c |
      c.getFunc().(Attribute).getName() in ["call", "run", "Popen"] and
      c.getArgByName("shell").(NameConstant).getValue() = true and
      sink.asExpr() = c.getArg(0)
    )
  }

  // Barriers: sanitization functions
  predicate isBarrier(DataFlow::Node node) {
    exists(Call c |
      c.getFunc().(Attribute).getObject().(Name).getId() = "shlex" and
      c.getFunc().(Attribute).getName() = "quote" and
      node.asExpr() = c
    )
    or
    exists(Call c |
      c.getFunc().(Name).getId() in ["sanitize", "escape", "validate"] and
      node.asExpr() = c
    )
  }

  // Custom flow steps (optional)
  predicate isAdditionalFlowStep(DataFlow::Node pred, DataFlow::Node succ) {
    exists(Call c |
      c.getFunc().(Attribute).getName() = "format" and
      pred.asExpr() = c.getFunc().(Attribute).getObject() and
      succ.asExpr() = c
    )
  }
}

module VariantFlow = TaintTracking::Global<VariantConfig>;
import VariantFlow::PathGraph

from VariantFlow::PathNode source, VariantFlow::PathNode sink
where VariantFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Potential variant: tainted data from $@ flows to dangerous sink.",
  source.getNode(), "user-controlled input"
