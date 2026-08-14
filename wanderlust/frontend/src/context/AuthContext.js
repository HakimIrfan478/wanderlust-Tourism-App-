import React, { createContext, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthAPI } from '../api/services';
import { TOKEN_KEY, REFRESH_KEY } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  // On app start, restore any saved session.
  useEffect(() => {
    (async () => {
      const token = await AsyncStorage.getItem(TOKEN_KEY);
      if (token) {
        try {
          const res = await AuthAPI.me();
          setUser(res.data);
        } catch (e) {
          await AsyncStorage.multiRemove([TOKEN_KEY, REFRESH_KEY]);
        }
      }
      setBooting(false);
    })();
  }, []);

  const login = async (username, password) => {
    const res = await AuthAPI.login(username, password);
    await AsyncStorage.setItem(TOKEN_KEY, res.data.access);
    await AsyncStorage.setItem(REFRESH_KEY, res.data.refresh);
    const me = await AuthAPI.me();
    setUser(me.data);
    return me.data;
  };

  const register = async (payload) => {
    await AuthAPI.register(payload);
    // auto-login after successful registration
    return login(payload.username, payload.password);
  };

  const refreshUser = async () => {
    const me = await AuthAPI.me();
    setUser(me.data);
    return me.data;
  };

  const logout = async () => {
    await AsyncStorage.multiRemove([TOKEN_KEY, REFRESH_KEY]);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, booting, login, register, logout, refreshUser, setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
