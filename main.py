import sys
import os
from time import strftime, gmtime

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

def main():
    app = QGuiApplication(sys.argv)

    curr_time = strftime("%H:%M:%S", gmtime())

    engine = QQmlApplicationEngine()
    engine.quit.connect(app.quit)
    engine.load('./UI/main.qml')
    engine.rootObjects()[0].setProperty('currTime', curr_time)

    sys.exit(app.exec())



if __name__ == "__main__":
    main()