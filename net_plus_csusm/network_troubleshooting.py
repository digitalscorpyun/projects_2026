# network_troubleshooting.py
# A parable of structural failure in four acts

class NetworkProblem:
    def __init__(self):
        self.symptoms = ["slow speeds", "dead jacks", "19 jacks on a 12-port switch"]
        self.suspects = ["wall plates", "cable terminations", "hidden infrastructure"]
        self.landlord = {"confidence": "high", "source": "nephew the electrician"}
        self.client = {"access": "limited", "patience": "waning"}
        self.mechanical_room = {"switch_ports": 12, "mystery": "link on 19 jacks"}

    def troubleshoot(self):
        # Step 1: Check the visible layer
        wall_plates = self.inspect("wall plates")
        if wall_plates.untwisted_inches > 1:
            return "Signal integrity compromised. Re-terminate."
        
        # Step 2: Follow the physical path
        ceiling_tiles = self.remove()
        if ceiling_tiles.reveals("hidden switch"):
            return "Infrastructure not documented. Centralize or label."
        
        # Step 3: Question assumptions
        if self.landlord["confidence"] == "high" and self.landlord["source"] == "nephew":
            return "Expertise assumed. Competence not verified."
        
        # Step 4: Fix the structure
        return self.reterminate_all() + self.consolidate_switches()

class HiddenSwitch:
    """
    A switch installed above ceiling tiles, undocumented, unreachable,
    terminated with two inches of untwisted pairs. It is not a mistake.
    It is the consequence of treating structured cabling as an afterthought.
    """
    def __init__(self):
        self.location = "above the ceiling"
        self.documentation = "none"
        self.terminations = "haphazard"
        self.function = "partial"
    
    def reveal(self):
        return "The switch was always there. The installer hoped no one would look up."

def lesson():
    print("The nephew was an electrician, not a network technician.")
    print("The landlord trusted family over facts.")
    print("The clients suffered the consequences.")
    print("The hidden switch was found when someone finally looked.")
    print("The network worked when the structure was fixed.")