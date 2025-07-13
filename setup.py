from setuptools import setup, find_packages

setup(
    name="palio-bot",
    version="0.1.0",
    description="Sistema di gestione dati del palio tramite linguaggio naturale",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0",
        "aiofiles>=23.0.0",
        "python-telegram-bot>=20.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "palio-cli=palio_bot.cli:main",
            "palio-telegram=palio_bot.telegram_bot:main",
        ],
    },
)