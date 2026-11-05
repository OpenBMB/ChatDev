# Common Issues

## SDK initializes but join fails

- Verify auth callback success before join.
- Validate meeting number/passcode format.
- Confirm role and host-specific fields for start flow.

## Native addon load failures

- Check Electron/Node ABI compatibility.
- Rebuild native modules for your Electron version.
- Confirm platform binaries are present in package/runtime paths.

## Callback silence or partial feature behavior

- Ensure controller callbacks are registered before invoking actions.
- Avoid duplicate singleton initialization in multiple processes.
- Confirm feature availability for account type/meeting type.

## Raw data instability

- Apply bounded queues and worker separation.
- Reduce frame sampling rates if renderer/main process saturates.
- Ensure graceful unsubscription on leave/cleanup.
