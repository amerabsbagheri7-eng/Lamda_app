[app]
title = لمدا
package.name = lamdaapp
package.domain = org.lamda
source.dir = .
source.include_exts = py,kv,png,jpg,ttf
version = 1.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2

[app:android]
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
