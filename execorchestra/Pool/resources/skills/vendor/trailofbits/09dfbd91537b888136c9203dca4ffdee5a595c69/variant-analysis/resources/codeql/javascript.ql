/**
 * @name [VARIANT_NAME]
 * @description Find variants of [ORIGINAL_BUG_ID]
 * @kind path-problem
 * @problem.severity error
 * @tags security variant-analysis
 */

import javascript
import semmle.javascript.security.dataflow.CommandInjectionQuery
import DataFlow::PathGraph

module VariantConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // Express request params
    exists(PropAccess pa |
      pa.getPropertyName() in ["query", "body", "params", "cookies"] and
      source.asExpr() = pa
    )
    or
    // URL/location
    exists(PropAccess pa |
      pa.getBase().toString() in ["window", "document", "location"] and
      source.asExpr() = pa
    )
  }

  predicate isSink(DataFlow::Node sink) {
    // Command injection
    exists(CallExpr c |
      c.getCalleeName() in ["exec", "execSync", "spawn", "spawnSync"] and
      sink.asExpr() = c.getArgument(0)
    )
    or
    // eval/Function
    exists(CallExpr c |
      c.getCalleeName() in ["eval", "Function"] and
      sink.asExpr() = c.getArgument(0)
    )
    or
    // SQL queries
    exists(CallExpr c |
      c.getCalleeName() in ["query", "raw", "execute"] and
      sink.asExpr() = c.getArgument(0)
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(CallExpr c |
      c.getCalleeName() in ["escape", "sanitize", "parseInt", "encodeURIComponent"] and
      node.asExpr() = c
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
