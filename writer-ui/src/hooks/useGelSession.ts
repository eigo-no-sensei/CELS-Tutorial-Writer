import { useEffect, useState } from 'react';
import { sessionStatus } from '../api';

export function useGelSession() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    sessionStatus().then((status) => {
      setIsAuthenticated(status.authenticated);
    }).catch(() => {
      setIsAuthenticated(false);
    });
  }, []);

  return { isAuthenticated };
}
