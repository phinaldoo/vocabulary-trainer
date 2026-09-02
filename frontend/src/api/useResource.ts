import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './client';
import { translateCurrent } from '../i18n';

export function useResource<T>(loader: () => Promise<T>, key = 'default') {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    void loaderRef.current()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof ApiError ? caught.message : translateCurrent('common.dataLoadError'));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [key, revision]);

  return { data, setData, loading, error, reload };
}
