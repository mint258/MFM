"""Close the frame-integration item at the taskbook's two-failure boundary."""
import pickle
from stage0_cohort import R,O,save
B=R/'MFM_p_data_information'
def main():
 with (O/'source_selected_unique_permutations.pkl').open('rb') as stream:m=pickle.load(stream)
 save(B/'results/p_data_information/source_atom_correspondence.json',dict(status='COMPLETE_UNIQUE_ATOM_MAPS; ORIGINAL_VECTOR_FRAME_INTEGRATION_UNRESOLVED_AFTER_TWO_FAILED_RUNS',permutation_metadata=m['stats'],native_base_geometry_cache=str(O/'source_selected_native_geometries.pkl'),frame_failures=[dict(log=str(O/'source_native_context.log'),exception='AttributeError: rdkit.Chem not imported'),dict(log=str(O/'source_native_context_retry.log'),exception='FileNotFoundError: output cache parent absent')],third_frame_attempt=False,reason='Taskbook per-item consecutive-failure limit; implementation failure is not evidence that the dataset is physically undefined',independent_continuation='Original coordinate-independent atomic/pair scalar projection uses already validated unique permutations; vector statistics remain explicitly at pilot aligned-label layer',original_input_2B_case_evidence='results/p_data_information/calibration_2B.json'))
 print('SOURCE_FRAME_ITEM_CLOSED_WITH_UNRESOLVED_STATUS')
if __name__=='__main__':main()