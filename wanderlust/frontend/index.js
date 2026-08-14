// Application entry point.
//
// `@expo/metro-runtime` must be imported before anything else: it installs the
// web runtime (fast refresh, the DOM root, error overlay) that Expo SDK 50+
// expects. Without it the web bundle loads but never mounts, so the page stays
// blank. It is a no-op on Android and iOS.
import '@expo/metro-runtime';

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App)
// and, on web, mounts into the #root element.
registerRootComponent(App);
