/**
 * @name [VARIANT_NAME]
 * @description Find variants of [ORIGINAL_BUG_ID]
 * @kind path-problem
 * @problem.severity error
 * @tags security variant-analysis
 */

import java
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import DataFlow::PathGraph

module VariantConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // HttpServletRequest.getParameter/getHeader
    exists(MethodAccess ma |
      ma.getMethod().getName() in ["getParameter", "getHeader", "getCookies", "getQueryString"] and
      ma.getMethod().getDeclaringType().getASupertype*().hasQualifiedName("javax.servlet", "ServletRequest") and
      source.asExpr() = ma
    )
    or
    // Spring @RequestParam, @PathVariable
    exists(Parameter p |
      p.getAnAnnotation().getType().hasQualifiedName("org.springframework.web.bind.annotation", ["RequestParam", "PathVariable", "RequestBody"]) and
      source.asParameter() = p
    )
  }

  predicate isSink(DataFlow::Node sink) {
    // Command injection
    exists(MethodAccess ma |
      ma.getMethod().hasQualifiedName("java.lang", "Runtime", "exec") and
      sink.asExpr() = ma.getArgument(0)
    )
    or
    exists(ClassInstanceExpr cie |
      cie.getConstructedType().hasQualifiedName("java.lang", "ProcessBuilder") and
      sink.asExpr() = cie.getArgument(0)
    )
    or
    // SQL injection
    exists(MethodAccess ma |
      ma.getMethod().getName() in ["executeQuery", "executeUpdate", "execute"] and
      ma.getMethod().getDeclaringType().getASupertype*().hasQualifiedName("java.sql", "Statement") and
      sink.asExpr() = ma.getArgument(0)
    )
    or
    // Path traversal
    exists(ClassInstanceExpr cie |
      cie.getConstructedType().hasQualifiedName("java.io", "File") and
      sink.asExpr() = cie.getArgument(0)
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(MethodAccess ma |
      ma.getMethod().getName() in ["escape", "sanitize", "parseInt", "valueOf"] and
      node.asExpr() = ma
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
