# Contexto del Proyecto AppFinanzas

Este documento describe la estructura y los componentes principales del proyecto `AppFinanzas`.

## Estructura de Directorios

```
/Users/xavier/Proyecto Flet/AppFinanzas/
├── components/             # Componentes reutilizables de la UI
├── fletapp-b39c2-firebase-adminsdk-fbsvc-c36b346f8b.json # Archivo de credenciales de Firebase Admin SDK
├── main.py                 # Punto de entrada principal de la aplicación Flet
├── models/                 # Definiciones de modelos de datos
├── requirements.txt        # Dependencias del proyecto Python
├── services/               # Módulos de servicio para interactuar con APIs externas (ej. Firebase)
│   ├── __pycache__/        # Archivos compilados de Python
│   └── firebase_service.py # Servicio para la autenticación y base de datos de Firebase
├── storage/                # Almacenamiento de datos local o temporal
│   ├── data/               # Datos persistentes
│   └── temp/               # Archivos temporales
├── utils/                  # Utilidades y funciones auxiliares
│   ├── __pycache__/        # Archivos compilados de Python
│   └── calculations.py     # Funciones de cálculo
└── views/                  # Vistas de la aplicación (páginas/pantallas)
    ├── __pycache__/        # Archivos compilados de Python
    ├── add_transaction_view.py # Vista para añadir transacciones
    ├── dashboard_view.py       # Vista del panel principal
    ├── edit_transaction_view.py # Vista para editar transacciones
    ├── login_view.py           # Vista de inicio de sesión
    ├── reports_view.py         # Vista de informes
    └── signup_view.py          # Vista de registro de usuario
```

## Descripción de Componentes Clave

- **`main.py`**: Es el archivo principal que inicializa la aplicación Flet y gestiona la navegación entre las diferentes vistas.
- **`fletapp-b39c2-firebase-adminsdk-fbsvc-c36b346f8b.json`**: Contiene las credenciales necesarias para que el SDK de Firebase Admin se autentique con tu proyecto de Firebase. Es crucial para operaciones de backend seguras.
- **`services/firebase_service.py`**: Este módulo maneja toda la lógica de interacción con Firebase, incluyendo autenticación de usuarios (inicio de sesión, registro) y operaciones con la base de datos Firestore.
- **`views/`**: Contiene los diferentes módulos que representan las pantallas o páginas de la aplicación. Cada archivo `_view.py` define la interfaz de usuario y la lógica específica de esa pantalla.
- **`components/`**: Aquí se encuentran los elementos de UI reutilizables que se utilizan en varias vistas para mantener la consistencia y facilitar el desarrollo.
- **`models/`**: Define las estructuras de datos o clases que representan las entidades de la aplicación (ej. `Transaction`, `User`).
- **`utils/calculations.py`**: Contiene funciones genéricas que realizan cálculos o transformaciones de datos que pueden ser utilizadas en diferentes partes de la aplicación.
- **`storage/`**: Directorios para almacenar datos o archivos temporales que la aplicación pueda necesitar.

Este proyecto parece ser una aplicación de gestión financiera construida con Flet, que utiliza Firebase para la autenticación y el almacenamiento de datos.