import savant_rs
from omegaconf import OmegaConf


if __name__ == "__main__":
    print(f"savant_rs verion: {savant_rs.version()}")
    print(f"OmegaConf: {OmegaConf.create()}")
