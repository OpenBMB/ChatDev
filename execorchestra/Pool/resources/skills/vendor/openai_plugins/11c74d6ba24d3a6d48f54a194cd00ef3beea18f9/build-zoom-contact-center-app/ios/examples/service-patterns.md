# iOS Service Patterns

## Context Setup

```swift
let context = ZoomCCContext()
context.cacheFolder = NSSearchPathForDirectoriesInDomains(.documentDirectory, .userDomainMask, true).first!
context.userName = userName
context.domainType = .US01
ZoomCCInterface.sharedInstance().context = context
```

## Chat Pattern

```swift
let item = ZoomCCItem()
item.sdkType = .chat
item.entryId = chatEntryId

let chat = ZoomCCInterface.sharedInstance().chatService()
chat.chatDelegate = self
if chat.status == .initial {
    chat.initialize(with: item)
    chat.login()
}
chat.fetchUI { vc in
    if let vc { self.navigationController?.pushViewController(vc, animated: true) }
}
```

## Video Pattern

```swift
let item = ZoomCCItem()
item.sdkType = .video
item.entryId = videoEntryId

let video = ZoomCCInterface.sharedInstance().videoService()
video.videoDelegate = self
if video.status == .initial {
    video.initialize(with: item)
}
video.fetchUI { vc in
    if let vc { self.navigationController?.pushViewController(vc, animated: true) }
}
```

## Scheduled Callback Pattern

```swift
let item = ZoomCCItem()
item.sdkType = .scheduledCallback
item.apiKey = callbackApiKey

let scheduled = ZoomCCInterface.sharedInstance().scheduledCallbackService()
scheduled.scheduledCallbackDelegate = self
if scheduled.status == .initial {
    scheduled.initialize(with: item)
}
scheduled.fetchUI { vc in
    if let vc { self.navigationController?.pushViewController(vc, animated: true) }
}
```

## Rejoin Pattern

```swift
func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
    return rootVC.handleRejoinVideoOpenURL(url)
}
```
