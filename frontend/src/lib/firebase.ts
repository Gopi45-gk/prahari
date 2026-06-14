// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";
import { getMessaging, isSupported } from "firebase/messaging";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyCk9rbKV_PlKQAexW9Sk4M7aAIttlzO8rM",
  authDomain: "prahari-authority.firebaseapp.com",
  projectId: "prahari-authority",
  storageBucket: "prahari-authority.firebasestorage.app",
  messagingSenderId: "289956414941",
  appId: "1:289956414941:web:b745c4e75a4e270ddc6234",
  measurementId: "G-P76E2WK6EQ"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = typeof window !== 'undefined' ? getAnalytics(app) : null;
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app);

// Initialize messaging only if supported (browser env)
let messaging: any = null;
if (typeof window !== 'undefined') {
  isSupported().then((supported) => {
    if (supported) {
      messaging = getMessaging(app);
    }
  });
}

export { app, analytics, auth, db, storage, messaging };
