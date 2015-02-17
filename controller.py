
import sys, os
import subprocess as sub
import random as r
import time as t

verbose = False

def pos_to_str(pos):
    if pos is None:
        return "N"
    else:
        return "%d,%d"%pos

class Bot:
    "A bot."

    def __init__(self, name, command, initial=None):
        self.name = name
        self.command = command
        self.initial = initial
        self.score = 0
        self.delta_score = 0
        self.handle = None
        self.enemies = None
        self.last_choice = None
        self.report = None

class Vertex:
    "A vertex."

    INACTIVE, ACTIVE, BROKEN = 0, 1, 2

    def __init__(self, children):
        self.children = children
        self.is_sink = not children
        self.status = self.INACTIVE
        self.owners = set()

def open_bots(bot_path):
    global verbose
    alp = list("abcdefghijklmnopqrstuvwxyz")
    bots = []
    bot_file = open(bot_path)
    while True:
        line = bot_file.readline()
        if not line:
            break
        if line[0] == '#':
            continue
        bot_name = line[:-1]
        command = bot_file.readline()[:-1]
        if verbose:
            bots.append(Bot(bot_name, command, initial=alp.pop(0)))
        else:
            bots.append(Bot(bot_name, command))
    bot_file.close()
    for i in range(len(bots)):
        order = list(range(len(bots)))
        order.remove(i)
        r.shuffle(order)
        bots[i].enemies = [bots[j] for j in order]
    return bots
        
def run_round(bots):
    slows = set()
    # Initial message: number of bots, number of turns, sidelength
    turns = len(bots)**2
    side = 2*turns
    for bot in bots:
        bot.handle = sub.Popen(bot.command.split(), bufsize=1, universal_newlines=True, stdin=sub.PIPE, stdout=sub.PIPE)
        bot.report = "BEGIN %d %d %d\n"%(len(bots), turns, side)
    grid = [[0]*side for y in range(side)]
    for y in reversed(range(side)):
        for x in range(side):
            grid[y][x] = Vertex([] if y == side-1 else [grid[y+1][(x-1)%side], grid[y+1][x], grid[y+1][(x+1)%side]])
    for turn in range(turns):
        # Destruction phase
        for bot in bots:
            bot.last_choice = None
            time = t.time()
            bot.handle.stdin.write(bot.report)
            bot.handle.stdin.write("DESTROY %d\n"%(turn,))
            response = bot.handle.stdout.readline()
            if t.time() - time > 2:
                print("  Bot %s was too slow to destroy."%(bot.name,))
                slows.add(bot)
            if response[:6] == "VERTEX":
                pos = (x,y) = tuple(map(int, response[7:].split(",")))
                if grid[y][x].status == Vertex.INACTIVE:
                    grid[y][x].status = Vertex.BROKEN
                    bot.last_choice = pos
        # Make destruction reports
        for bot in bots:
            bot.report = "BROKEN %d %s %s\n"%(turn, pos_to_str(bot.last_choice), " ".join(pos_to_str(enemy.last_choice) for enemy in bot.enemies))
        # Activation phase
        activated = set()
        for bot in bots:
            bot.last_choice = None
            time = t.time()
            bot.handle.stdin.write(bot.report)
            bot.handle.stdin.write("ACTIVATE %d\n"%(turn,))
            response = bot.handle.stdout.readline()
            if t.time() - time > 2:
                print("  Bot %s was too slow to claim."%(bot.name,))
                slows.add(bot)
            if response[:6] == "VERTEX":
                pos = (x,y) = tuple(map(int, response[7:].split(",")))
                if grid[y][x].status == Vertex.INACTIVE:
                    grid[y][x].owners.add(bot)
                    activated.add(pos)
                    bot.last_choice = pos
        for (x,y) in activated:
            grid[y][x].status = Vertex.ACTIVE
        # Make activation reports
        for bot in bots:
            bot.report = "OWNED %d %s %s\n"%(turn, pos_to_str(bot.last_choice), " ".join(pos_to_str(enemy.last_choice) for enemy in bot.enemies))
    # Compute scores by DFS
    print("  Finished, computing score.")
    if verbose:
        for row in reversed(grid):
            print("  " + "".join([r.sample(list(v.owners), 1)[0].initial if v.status == Vertex.ACTIVE else ("." if v.status == Vertex.INACTIVE else " ") for v in row]))
    for bot in bots:
        bot.delta_score = 0
    for x in range(side):
        if grid[0][x].status != Vertex.ACTIVE:
            continue
        for i in range(len(bots)):
            visited = set()
            cell = grid[0][x]
            succs = [child for child in cell.children if child.status == Vertex.ACTIVE]
            r.shuffle(succs)
            path = [(cell, succs)]
            while path:
                cell, children = path[0]
                if cell.is_sink:
                    break
                if children:
                    child = children.pop(0)
                    if child not in visited:
                        succs = [gchild for gchild in child.children if gchild.status == Vertex.ACTIVE]
                        r.shuffle(succs)
                        path = [(child, succs)] + path
                        visited.add(child)
                else:
                    path = path[1:]
            if path:
                for (cell, c) in path:
                    for bot in cell.owners:
                        bot.score += 1
                        bot.delta_score += 1
    # Report back scores
    for bot in bots:
        message = "SCORE %d %s\n"%(bot.delta_score, " ".join(str(enemy.delta_score) for enemy in bot.enemies))
        time = t.time()
        bot.handle.stdin.write(bot.report)
        bot.handle.stdin.write(message)
        bot.handle.stdin.close()
        bot.handle.wait()
        if t.time() - time > 1:
            print("  Bot %s was too slow to halt."%(bot.name,))
            slows.add(bot)
    return slows

def main():
    global verbose
    if len(sys.argv) > 1:
        rounds = int(sys.argv[-1])
    else:
        rounds = 100
    if "-v" in sys.argv:
        verbose = True
    print("Initializing bots.")
    for bot_dir in os.listdir("bots"):
        open(os.path.join("bots", bot_dir, "data.txt"), "w").close()
    bots = open_bots("bots.txt")
    print("Bots:")
    for bot in bots:
        if verbose:
            print("  %s (%s)"%(bot.name, bot.initial))
        else:
            print("  " + bot.name)
    print("Running %d rounds."%(rounds,))
    slow_bots = set()
    for i in range(rounds):
        print("  Round %d"%(i,))
        slow_bots.update(run_round(bots))
        print("  Results: " + " ".join(str(bot.delta_score) for bot in bots))
    print("Final results:")
    for bot in sorted(bots, key=lambda b: -b.score):
        print("  %s: %d"%(bot.name, bot.score))
    if slow_bots:
        print("The following bots were too slow:")
        for bot in slow_bots:
            print("  " + bot.name)
    

if __name__ == "__main__":
    main()
