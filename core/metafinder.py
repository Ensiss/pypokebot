import numpy as np
import database; db = database.Database
import core.io; io = core.io.IO

class Metafinder:
    class MetaMemory:
        def __init__(self):
            self.visited = set()

    visited = {} # Dict of pair accessibility within a map

    def _subSearch(start_key, tgt_key, path, meta_mem):
        (xe, ye, bide, mide) = tgt_key
        to_visit = [(start_key, [])]
        while len(to_visit):
            curr_key, path = to_visit.pop(0)
            (xc, yc, bidc, midc) = curr_key
            # TODO: check path accessibility before returning
            if bidc == bide and midc == mide:
                return path
            m = db.banks[bidc][midc]
            # finder = m.getPathfinder()
            # Explore map connections
            for conn in m.connects:
                # TODO: conn.exits should not have 0 length
                # TODO: investigate for map [3,41]
                if len(conn.exits) == 0:
                    continue
                # TODO: can a connection lead to different parts of a map?
                exit_x, exit_y = conn.exits[0]
                # Sometimes
                entry_x, entry_y = conn.getMatchingEntry(exit_x, exit_y)
                conn_key = (exit_x, exit_y, bidc, midc)
                dest_key = (entry_x, entry_y, conn.bank_id, conn.map_id)
                if dest_key in meta_mem.visited:
                    continue
                meta_mem.visited.add(conn_key)
                meta_mem.visited.add(dest_key)
                to_visit.append((dest_key, path + [(conn.bank_id, conn.map_id)]))
            # Explore warps
            for warp in m.warps:
                dest_warp = db.banks[warp.dest_bank][warp.dest_map].warps[warp.dest_warp]
                # TODO: dest_warp.dest_warp should be valid
                # TODO: investigate for map [0,1]
                if dest_warp.dest_warp > len(m.warps):
                    continue
                back_warp = m.warps[dest_warp.dest_warp]
                warp_key = (back_warp.x, back_warp.y, bidc, midc)
                dest_key = (dest_warp.x, dest_warp.y, warp.dest_bank, warp.dest_map)
                if dest_key in meta_mem.visited:
                    continue
                meta_mem.visited.add(warp_key)
                meta_mem.visited.add(dest_key)
                to_visit.append((dest_key, path + [(warp.dest_bank, warp.dest_map)]))
        return None

    def search(xs, ys, bids, mids, xe, ye, bide, mide):
        meta_mem = Metafinder.MetaMemory()
        curr_key = (xs, ys, bids, mids)
        tgt_key = (xe, ye, bide, mide)
        return Metafinder._subSearch(curr_key, tgt_key, [], meta_mem)

    def searchFromPlayer(xe, ye, bide, mide):
        p = db.player
        return Metafinder.search(p.x, p.y, p.bank_id, p.map_id, xe, ye, bide, mide)
