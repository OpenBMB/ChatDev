import yaml from 'js-yaml'

// Converts form data to YAML string of graph
export function convertFormDataToYAML(formData) {
  const yamlObject = {
    version: '0.4.0',
    graph: {
      id: formData.id.trim(),
      description: formData.description.trim() || null,
      initial_instruction: formData.initial_instruction.trim() || null,
      log_level: 'INFO',
      is_majority_voting: false,
      end: [],
      memories: [],
      nodes: [],
      edges: []
    }
  }
  
  yamlObject.graph.memories = formData.memories || []
  
  // Data exists as [{key, value}] in form, convert to {key: value} in YAML
  if (formData.vars && formData.vars.length > 0) {
    yamlObject.graph.vars = {}
    formData.vars.forEach(varItem => {
      yamlObject.graph.vars[varItem.key] = varItem.value
    })
  }
  
  return yaml.dump(yamlObject, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false
  })
}


