import sys

from train_debug import main


if __name__ == "__main__":
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "mt"])
    main()
