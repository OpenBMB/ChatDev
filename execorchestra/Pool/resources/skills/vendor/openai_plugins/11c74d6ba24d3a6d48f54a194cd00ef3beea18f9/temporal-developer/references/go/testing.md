# Go SDK Testing

## Overview

The Go SDK provides the `testsuite` package for testing Workflows and Activities. It uses the [testify](https://github.com/stretchr/testify) library for assertions (`assert`/`require`) and mocking (`mock`). The test environment supports automatic time-skipping for Workflows with timers.

## Test Environment Setup

Two approaches: struct-based with `suite.Suite` or function-based with `testsuite.NewTestWorkflowEnvironment()`.

**Approach 1: Struct-based (testify suite)**

```go
package sample

import (
	"testing"

	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/suite"

	"go.temporal.io/sdk/testsuite"
)

type UnitTestSuite struct {
	suite.Suite
	testsuite.WorkflowTestSuite

	env *testsuite.TestWorkflowEnvironment
}

func (s *UnitTestSuite) SetupTest() {
	s.env = s.NewTestWorkflowEnvironment()
}

func (s *UnitTestSuite) AfterTest(suiteName, testName string) {
	s.env.AssertExpectations(s.T())
}

func (s *UnitTestSuite) Test_MyWorkflow_Success() {
	s.env.ExecuteWorkflow(MyWorkflow, "input")

	s.True(s.env.IsWorkflowCompleted())
	s.NoError(s.env.GetWorkflowError())
}

func TestUnitTestSuite(t *testing.T) {
	suite.Run(t, new(UnitTestSuite))
}
```

**Approach 2: Function-based**

```go
package sample

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"go.temporal.io/sdk/testsuite"
)

func Test_MyWorkflow(t *testing.T) {
	testSuite := &testsuite.WorkflowTestSuite{}
	env := testSuite.NewTestWorkflowEnvironment()
	env.RegisterActivity(MyActivity)

	env.ExecuteWorkflow(MyWorkflow, "input")
	assert.True(t, env.IsWorkflowCompleted())
	assert.NoError(t, env.GetWorkflowError())

	var result string
	assert.NoError(t, env.GetWorkflowResult(&result))
	assert.Equal(t, "expected", result)
}
```

You must register all Activity Definitions used by the Workflow with `env.RegisterActivity(ActivityFunc)`. The Workflow itself does not need to be registered.

## Activity Mocking

Mock activities with `env.OnActivity()` to test Workflow logic in isolation.

**Return mock values:**

```go
env.OnActivity(MyActivity, mock.Anything, mock.Anything).Return("mock_result", nil)
```

**Return a function replacement** (for parameter validation or custom logic):

```go
env.OnActivity(MyActivity, mock.Anything, mock.Anything).Return(
	func(ctx context.Context, input string) (string, error) {
		// Custom logic, assertions, etc.
		return "computed_result", nil
	},
)
```

**Match specific arguments:**

```go
env.OnActivity(MyActivity, mock.Anything, "specific_input").Return("result", nil)
```

When using mocks, you do not need to call `env.RegisterActivity()` for that Activity. The mock signature must match the original Activity function signature.

## Testing Signals and Queries

Use `RegisterDelayedCallback` to send Signals during Workflow execution. Use `QueryWorkflow` to test query handlers.

```go
func (s *UnitTestSuite) Test_SignalsAndQueries() {
	// Register a delayed callback to send a signal after 5 seconds
	s.env.RegisterDelayedCallback(func() {
		s.env.SignalWorkflow("approve", SignalData{Approved: true})
	}, time.Second*5)

	s.env.ExecuteWorkflow(ApprovalWorkflow, input)

	s.True(s.env.IsWorkflowCompleted())
	s.NoError(s.env.GetWorkflowError())
}
```

**Query a running Workflow** (must be called inside `RegisterDelayedCallback` or after `ExecuteWorkflow`):

```go
s.env.RegisterDelayedCallback(func() {
	res, err := s.env.QueryWorkflow("getProgress")
	s.NoError(err)

	var progress int
	err = res.Get(&progress)
	s.NoError(err)
	s.Equal(50, progress)
}, time.Second*10+time.Millisecond)
```

`QueryWorkflow` returns a `converter.EncodedValue`. Use `.Get(&result)` to decode the value.

For "Signal-With-Start" testing, set the delay to `0`.

## Testing Failure Cases

```go
func (s *UnitTestSuite) Test_WorkflowFailure() {
	// Mock activity to return an error
	s.env.OnActivity(MyActivity, mock.Anything, mock.Anything).Return(
		"", errors.New("activity failed"))

	s.env.ExecuteWorkflow(MyWorkflow, "input")

	s.True(s.env.IsWorkflowCompleted())

	err := s.env.GetWorkflowError()
	s.Error(err)

	var applicationErr *temporal.ApplicationError
	s.True(errors.As(err, &applicationErr))
	s.Equal("activity failed", applicationErr.Error())
}
```

`env.GetWorkflowError()` returns the Workflow error. Use `errors.As(err, &applicationErr)` to check the error type. Mock activities returning errors to test Workflow error-handling paths.

## Replay Testing

Use `worker.NewWorkflowReplayer()` to verify that code changes do not break determinism. Load history from a JSON file exported via the Temporal CLI or Web UI.

```go
package sample

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"go.temporal.io/sdk/worker"
)

func Test_ReplayFromFile(t *testing.T) {
	replayer := worker.NewWorkflowReplayer()
	replayer.RegisterWorkflow(MyWorkflow)

	err := replayer.ReplayWorkflowHistoryFromJSONFile(nil, "my_workflow_history.json")
	assert.NoError(t, err)
}
```

Export history via CLI: `temporal workflow show --workflow-id <id> --output json > history.json`

**Replay from a programmatically fetched history:**

```go
func Test_ReplayFromServer(t *testing.T) {
	// Fetch history from the server
	hist, err := GetWorkflowHistory(ctx, client, workflowID, runID)
	assert.NoError(t, err)

	replayer := worker.NewWorkflowReplayer()
	replayer.RegisterWorkflow(MyWorkflow)

	err = replayer.ReplayWorkflowHistory(nil, hist)
	assert.NoError(t, err)
}
```

## Activity Testing

Test Activities in isolation using `TestActivityEnvironment`. No Worker or Workflow needed.

```go
func Test_MyActivity(t *testing.T) {
	testSuite := &testsuite.WorkflowTestSuite{}
	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(MyActivity)

	val, err := env.ExecuteActivity(MyActivity, "input")
	assert.NoError(t, err)

	var result string
	assert.NoError(t, val.Get(&result))
	assert.Equal(t, "expected_output", result)
}
```

`ExecuteActivity` returns `(converter.EncodedValue, error)`. Use `val.Get(&result)` to extract the typed result. The Activity executes synchronously in the calling goroutine.

## Best Practices

1. Register all Activities used by the Workflow with `env.RegisterActivity()`, unless you mock them with `env.OnActivity()`
2. Use mocks to isolate Workflow logic from Activity implementations
3. Test failure paths by mocking Activities that return errors
4. Use replay testing before deploying Workflow code changes to catch non-determinism errors
5. Use unique task queues per test when running integration tests
6. Call `env.AssertExpectations(s.T())` in `AfterTest` to verify all mocks were called
