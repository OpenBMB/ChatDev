import yaml from 'js-yaml'

const apiUrl = (path) => path

const addYamlSuffix = (filename) => {
  const trimmed = (filename || '').trim()
  if (!trimmed) {
    return ''
  }
  if (trimmed.endsWith('.yaml') || trimmed.endsWith('.yml')) {
    return trimmed
  }
  return `${trimmed}.yaml`
}

// Upload a YAML file
export async function postYaml(filename, content) {
  try {
    const fullFilename = addYamlSuffix(filename)
    const response = await fetch(apiUrl('/api/workflows/upload/content'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        filename: fullFilename,
        content: content
      })
    })

    // Return 400 when content is invalid
    if (response.ok || response.status === 400) {
      const data = await response.json()

      // If status is missing, content validation failed and detail contains the error
      if (data.status) {
        return {
          success: true,
          message: 'YAML file saved successfully!'
        }
      } else if (data.detail) {
        return {
          success: false,
          detail: data.detail
        }
      } else {
        return {
          success: false,
          message: 'Unknown error saving YAML file'
        }
      }
    } else {
      const errorData = await response.json().catch(() => ({}))
      console.error('Error saving YAML file:', errorData)
      return {
        success: false,
        message: `Error saving YAML file: ${errorData.message || response.statusText}`
      }
    }
  } catch (error) {
    console.error('Error saving YAML file:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

export async function updateYaml(filename, content) {
  try {
    const yamlFilename = addYamlSuffix(filename)
    const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(yamlFilename)}`), {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content
      })
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        filename: data?.filename || yamlFilename,
        message: data?.message || 'Workflow updated successfully'
      }
    }

    return {
      success: false,
      detail: data?.detail,
      message: data.error?.message || 'Failed to update workflow',
      status: response.status
    }
  } catch (error) {
    console.error('Error updating workflow YAML:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Rename YAML file
export async function postYamlNameChange(filename, newFilename) {
  try {
    const yamlFilename = addYamlSuffix(filename)
    const yamlNewFilename = addYamlSuffix(newFilename)
    const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(yamlFilename)}/rename`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        new_filename: yamlNewFilename
      })
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        filename: data?.filename || yamlNewFilename,
        message: data?.message || 'Workflow renamed successfully'
      }
    }

    return {
      success: false,
      detail: data?.detail,
      message: data?.message || 'Failed to rename workflow',
      status: response.status
    }
  } catch (error) {
    console.error('Error renaming workflow YAML:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Copy YAML file
export async function postYamlCopy(filename, newFilename) {
  try {
    const yamlFilename = addYamlSuffix(filename)
    const yamlNewFilename = addYamlSuffix(newFilename)
    const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(yamlFilename)}/copy`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        new_filename: yamlNewFilename
      })
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        filename: data?.filename || yamlNewFilename,
        message: data?.message || 'Workflow copied successfully'
      }
    }

    return {
      success: false,
      detail: data?.detail,
      message: data?.message || 'Failed to copy workflow',
      status: response.status
    }
  } catch (error) {
    console.error('Error copying workflow YAML:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Load the YAML file list from the API with names and descriptions
export async function fetchWorkflowsWithDesc() {
  try {
    const response = await fetch(apiUrl('/api/workflows'))
    if (!response.ok) {
      throw new Error(`/api/workflows fetch error, status: ${response.status}`)
    }
    const data = await response.json()

    // Fetch YAML descriptions by filename
    const filesWithDesc = await Promise.all(
      data.workflows.map(async (filename) => {
        try {
          const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(filename)}`))
          const fileData = await response.json()
          return {
            name: filename,
            description: getYAMLDescription(fileData.content)
          }
        } catch {
          return { name: filename, description: 'No description' }
        }
      })
    )

    return {
      success: true,
      workflows: filesWithDesc
    }
  } catch (err) {
    console.error('Failed to load YAML files:', err)
    return {
      success: false,
      error: 'Failure loading YAML files, please run API service'
    }
  }

  function getYAMLDescription(content) {
    try {
      const doc = yaml.load(content)
      return doc.graph.description || 'No description'
    } catch {
      return 'No description'
    }
  }
}

// Fetch YAML file content
export async function fetchWorkflowYAML(filename) {
  try {
    const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(filename)}`))
    if (!response.ok) {
      throw new Error(`Failed to load YAML file: ${filename}, status: ${response.status}`)
    }
    const data = await response.json()
    return data.content
  } catch (err) {
    console.error('Failed to load YAML file:', err)
    throw err
  }
}

// Fetch YAML for the specified workflow
export async function fetchYaml(filename) {
  try {
    const yamlFilename = addYamlSuffix(filename)
    const response = await fetch(apiUrl(`/api/workflows/${encodeURIComponent(yamlFilename)}`))

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        content: data?.content
      }
    }

    return {
      success: false,
      detail: data?.detail,
      message: data?.message || 'Failed to fetch YAML file',
      status: response.status
    }
  } catch (error) {
    console.error('Error fetching YAML file:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Fetch the VueFlow graph
export async function fetchVueGraph(key) {
  try {
    const response = await fetch(apiUrl(`/api/vuegraphs/${encodeURIComponent(key)}`))
    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        content: data?.content,
        status: response.status
      }
    }

    return {
      success: false,
      status: response.status,
      detail: data?.detail,
      message: data?.message || 'Failed to fetch VueFlow graph'
    }
  } catch (error) {
    console.error('Error fetching VueFlow graph:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Save the VueFlow graph
export async function postVuegraphs({ filename, content }) {
  try {
    const response = await fetch(apiUrl('/api/vuegraphs/upload/content'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        filename,
        content
      })
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        message: data?.message || 'VueFlow graph saved successfully'
      }
    }

    return {
      success: false,
      status: response.status,
      detail: data?.detail,
      message: data?.message || 'Failed to save VueFlow graph'
    }
  } catch (error) {
    console.error('Error saving VueFlow graph:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Fetch the config schema
export async function fetchConfigSchema(breadcrumbs) {
  try {
    const response = await fetch(apiUrl('/api/config/schema'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        breadcrumbs: breadcrumbs
      })
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch config schema: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Failed to fetch config schema:', error)
    throw error
  }
}

// Download execution logs
export async function fetchLogsZip(sessionId) {
  try {
    const response = await fetch(apiUrl(`/api/sessions/${encodeURIComponent(sessionId)}/download`))

    if (!response.ok) {
      throw new Error(`Download failed: ${response.status} ${response.statusText}`)
    }

    // Get zip file data
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)

    // Create a download link and trigger download
    const link = document.createElement('a')
    link.href = url
    link.download = `execution_logs_${sessionId}.zip`
    document.body.appendChild(link)
    link.click()

    // Cleanup
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    return { success: true }
  } catch (error) {
    console.error('Failed to download execution logs:', error)
    throw error
  }
}

// Fetch session attachments
export async function getAttachment(sessionId, attachmentId) {
  try {
    if (!sessionId) {
      throw new Error('Missing session id')
    }
    if (!attachmentId) {
      throw new Error('Missing attachment id')
    }

    const response = await fetch(apiUrl(`/api/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(attachmentId)}`))

    if (!response.ok) {
      throw new Error(`Failed to fetch attachment: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data?.data_uri
  } catch (error) {
    console.error('Failed to fetch attachment:', error)
    throw error
  }
}

// Batch workflow execution
export async function postBatchWorkflow({ file, sessionId, yamlFile, maxParallel, logLevel }) {
  try {
    const formData = new FormData()

    // Append required parameters
    if (file) {
      formData.append('file', file)
    }
    if (sessionId) {
      formData.append('session_id', sessionId)
    }
    if (yamlFile) {
      formData.append('yaml_file', yamlFile)
    }
    if (maxParallel !== undefined) {
      formData.append('max_parallel', maxParallel.toString())
    }
    if (logLevel) {
      formData.append('log_level', logLevel)
    }

    const response = await fetch(apiUrl('/api/workflows/batch'), {
      method: 'POST',
      body: formData
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        message: data?.message || 'Batch workflow executed successfully',
        ...data
      }
    }

    return {
      success: false,
      detail: data?.detail,
      message: data?.message || 'Failed to execute batch workflow',
      status: response.status
    }
  } catch (error) {
    console.error('Error executing batch workflow:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}

// Upload a binary file
export async function postFile(sessionId, file) {
  try {
    if (!sessionId) {
      throw new Error('Missing session id')
    }

    if (!file) {
      throw new Error('Missing file payload')
    }

    const formData = new FormData()
    let payload = file
    let filename = 'upload.bin'

    if (typeof file === 'string') {
      payload = new Blob([file], { type: 'application/octet-stream' })
    } else if (file?.name) {
      filename = file.name
    }

    formData.append('file', payload, filename)

    const response = await fetch(apiUrl(`/api/uploads/${encodeURIComponent(sessionId)}`), {
      method: 'POST',
      body: formData
    })

    const data = await response.json().catch(() => ({}))

    if (response.ok) {
      return {
        success: true,
        message: 'File uploaded successfully',
        name: data?.name,
        attachmentId: data?.attachment_id,
        mimeType: data?.mime_type,
        size: data?.size
      }
    }

    return {
      success: false,
      message: 'Failed to upload file'
    }
  } catch (error) {
    console.error('Error uploading file:', error)
    return {
      success: false,
      message: 'API error'
    }
  }
}
