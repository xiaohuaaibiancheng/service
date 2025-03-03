class LazyModel:
    def __init__(self, init_func):
        self.init_func = init_func
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = self.init_func()
        return self._model

    def close(self):
        if self._model is not None:
            if hasattr(self._model, 'close'):
                self._model.close()
            self._model = None