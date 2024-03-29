import numpy as np
import database; db = database.Database
import core.io; io = core.io.IO
from script import Script
import world
import player

class Metafinder:
    subpaths = {} # Dict of pair accessibility within a map

    def _subSearch(start_key, checker):
        """
        Returns a valid path from start_key, validated by the function 'checker'
        start_key: (x, y, bank_id, map_id)
        checker:
        - called for each new visited node
        - args: list of nodes to visit, current node
        - returns: True if the current path has reached the target, False otherwise
        - notes: the checker should add a path to a precise location to 'to_visit' once the right map has been found
        """
        def checkPath(path):
            for node in path:
                if node in Metafinder.subpaths:
                    if Metafinder.subpaths[node]:
                        continue
                    else:
                        return False, node
                (xp, yp, bidp, midp), args = node
                m = db.banks[bidp][midp]
                finder = m.getPathfinder()
                ret = None
                if type(args) is world.Connection:
                    ret = finder.searchConnection(xp, yp, args)
                elif type(args) is world.WarpEvent:
                    max_dist = (m.map_status[args.y, args.x] == world.Status.OBSTACLE)
                    ret = finder.searchWarp(xp, yp, args, max_dist)
                elif type(args) is world.PersonEvent:
                    ret = finder.searchPers(xp, yp, args)
                else:
                    xe, ye = args
                    ret = finder.searchPos(xp, yp, xe, ye)
                Metafinder.subpaths[node] = (ret is not None)
                if ret is None:
                    return False, node
            return True, None

        to_visit = [(start_key, [], [])]
        while len(to_visit):
            curr_node = to_visit.pop(0)
            curr_key, path, meta_mem = curr_node
            (xc, yc, bidc, midc) = curr_key
            if checker(to_visit, curr_node):
                is_valid, failure_node = checkPath(path)
                if is_valid:
                    return path
                # Prune candidates containing the unreachable node
                to_visit = [cand for cand in to_visit if failure_node not in cand[1]]
                continue

            m = db.banks[bidc][midc]
            blacklist = set()
            # Explore map connections
            for conn in m.connects:
                # TODO: conn.exits should not have 0 length
                # TODO: investigate for map [3,41]
                dest_conn = conn.getMatchingConnection()
                if len(conn.exits) == 0 or len(dest_conn.exits) == 0:
                    continue
                # TODO: can a connection lead to different parts of a map?
                exit_x, exit_y = conn.exits[0]
                entry_x, entry_y = dest_conn.exits[0]
                conn_key = (exit_x, exit_y, bidc, midc)
                dest_key = (entry_x, entry_y, conn.dest_bank, conn.dest_map)
                if dest_key in meta_mem or dest_key in blacklist:
                    continue
                blacklist.add(dest_key)
                to_visit.append((dest_key,
                                 path + [(curr_key, conn)],
                                 meta_mem + [conn_key, dest_key]))
            # Explore warps
            blacklist = set()
            for warp in m.warps:
                dest_warp = db.banks[warp.dest_bank][warp.dest_map].warps[warp.dest_warp]
                # TODO: dest_warp.dest_warp should be valid
                # TODO: investigate for map [0,1]
                if dest_warp.dest_warp > len(m.warps):
                    continue
                back_warp = m.warps[dest_warp.dest_warp]
                warp_key = (back_warp.x, back_warp.y, bidc, midc)
                dest_key = (dest_warp.x, dest_warp.y, warp.dest_bank, warp.dest_map)
                if dest_key in meta_mem or dest_key in blacklist:
                    continue
                blacklist.add(dest_key)
                to_visit.append((dest_key,
                                 path + [(curr_key, back_warp)],
                                 meta_mem + [warp_key, dest_key]))
        return None

    def _getStart(info=None):
        if info is None:
            info = db.player
        if type(info) is player.Player:
            return info.x, info.y, info.bank_id, info.map_id
        elif type(info) is tuple:
            if len(info) != 4:
                print("Metafinder.getStart error: wrong info length:", info)
                return Metafinder._getStart()
            return info
        print("Metafinder.getStart error: invalid info:", info)
        return Metafinder._getStart()

    def search(xe, ye, bide, mide, start=None):
        def checker(to_visit, node, tgt_key):
            curr_key, path, meta_mem = node
            # Exact target has been reached
            if curr_key == tgt_key:
                return True
            (xc, yc, bidc, midc) = curr_key
            (xe, ye, bide, mide) = tgt_key
            # Destination map reached, add final path to the list
            if bidc == bide and midc == mide:
                to_visit.insert(0, (tgt_key,
                                    path + [(curr_key, (xe, ye))],
                                    meta_mem))
            return False

        start_key = Metafinder._getStart(start)
        tgt_key = (xe, ye, bide, mide)
        return Metafinder._subSearch(start_key, lambda *args: checker(*args, tgt_key))

    def searchMap(bank_id, map_id, start=None):
        def checker(to_visit, node):
            curr_key, path, meta_mem = node
            (xc, yc, bidc, midc) = curr_key
            # Destination map reached
            if bidc == bank_id and midc == map_id:
                return True
            return False
        start_key = Metafinder._getStart(start)
        return Metafinder._subSearch(start_key, checker)

    def searchHealer(start=None):
        def checker(to_visit, node):
            curr_key, path, meta_mem = node
            (xc, yc, bidc, midc) = curr_key
            m = db.banks[bidc][midc]
            heal_instr = Script.CallSpecial(0x0)
            # Exact target has been reached
            if len(path):
                key, args = path[-1]
                # TODO: execute script and check that the heal is reachable
                if type(args) is world.PersonEvent:
                    return True
            # Add final path to person if they can heal the party
            for pers in m.persons:
                if (pscript := Script.getPerson(pers.evt_nb-1, bidc, midc)) is None:
                    continue
                if heal_instr in pscript.outputs:
                    to_visit.insert(0, ((pers.x, pers.y, bidc, midc),
                                        path + [(curr_key, pers)],
                                        meta_mem))
            return False

        start_key = Metafinder._getStart(start)
        return Metafinder._subSearch(start_key, checker)
