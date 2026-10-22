"""D152 — two bugs found in run 71d2f910: (1) the cut marker D144/D147 put in a shortened result ("… [971 characters
cut; …]") was checked as text cited from a source; (2) a helper reply hit its length limit (5,222 visible + 2,970
thinking tokens = the 8,192 room) though an earlier reply of the same role group had already used 7,404 of it: the
room now follows the largest reply the group has needed in the run. Offline."""
from amoeba.interp.citecheck import mislabelled_citations
from amoeba.interp.trace import TracedLLM, TraceWriter
from amoeba.llm.client import ChatResponse

ROWS = "2026-03-30 | 4.512\n2026-04-06 | 4.498\n"


# ---- (1) the cut marker is not cited source text -------------------------------------------------------------------
def test_a_quoted_cut_marker_is_not_a_cited_claim():
    line = 'The printed output was cut off ("971 characters cut") [S24].'           # 71d2f910, step 1
    assert mislabelled_citations(line, {"S24": ROWS}) == []


def test_a_cut_note_with_a_saved_path_is_not_checked_but_the_figures_are():
    line = ("Weeks 2026-03-30 4.512 … [1,203 characters cut; [the whole page is in sources/S4_eia_2025.txt; open it "
            "with local:Read] …] and 4.40 [S24]")
    found = mislabelled_citations(line, {"S24": ROWS})
    assert [f["claim"] for f in found] == ["4.40"], found                   # the real figure is still checked


# ---- (2) the reply room follows what the role group needed -----------------------------------------------------------
class Sized:
    """A model whose replies need `need` tokens (visible + thinking); cut at the room it is given."""
    model = "sized"

    def __init__(self, needs):
        self.needs, self.rooms = list(needs), []

    def chat_messages(self, messages, seed=0, max_tokens=None, **kw):
        need = self.needs.pop(0)
        self.rooms.append(max_tokens)
        cut = max_tokens is not None and need > max_tokens
        used = min(need, max_tokens or need)
        return ChatResponse(content="ok", input_tokens=100, output_tokens=used - used // 3,
                            reasoning_tokens=used // 3, finish_reason="length" if cut else "stop")


def call(llm, role="workers"):
    return llm.chat_messages([{"role": "user", "content": "go"}], max_tokens=8192, role=role)


def test_a_group_that_came_close_to_its_room_gets_more_next_time():
    model = Sized([7404, 8400, 8400])                            # 71d2f910: row 310 used 7,404; row 627 needed more
    llm = TracedLLM(model, TraceWriter(None, episode_id="d152"))
    call(llm)
    r = call(llm)
    assert r.finish_reason == "stop" and len(model.rooms) == 2, model.rooms   # no cut reply, no retry
    assert model.rooms[1] >= int(1.5 * 7404)


def test_the_room_never_shrinks_below_the_callers_and_is_capped_and_per_group():
    model = Sized([20000, 20000, 100, 100])
    llm = TracedLLM(model, TraceWriter(None, episode_id="d152b"))
    call(llm)                                                    # cut at 8,192, retried with 16,384 (D27), cut again
    call(llm)
    call(llm, role="reviewers")
    assert model.rooms[2] == 16384                               # at most the D27 retry room
    assert model.rooms[3] == 8192                                # another role group keeps the caller's room
