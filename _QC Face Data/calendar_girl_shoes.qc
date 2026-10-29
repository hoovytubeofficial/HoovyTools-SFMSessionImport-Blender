// Created by Crowbar 0.74

$modelname "build_your_human/hwm/calendar_girl_feet.mdl"

$model "PosterGirl_Hair" "PosterGirl_Hair.smd" {

	mouth 0 "mouth" "bip_head" 0 1 0
}
$model "PosterGirl_Body" "PosterGirl_Body_Feet.smd" {

	flexfile "calendar_girl_feet_02.vta" 
	{
		defaultflex frame 0
		flex "LongNails" frame 1
	}

	flexcontroller LongNails range 0 1 "LongNails"
	flexcontroller right_CloseLid range -1 1 "right_CloseLid"
	flexcontroller left_CloseLid range -1 1 "left_CloseLid"
	flexcontroller multi_CloseLid range -1 1 "multi_CloseLid"
	flexcontroller blink range 0 1 "blink"
	flexcontroller right_InnerSquint range 0 1 "right_InnerSquint"
	flexcontroller left_InnerSquint range 0 1 "left_InnerSquint"
	flexcontroller right_OuterSquint range 0 1 "right_OuterSquint"
	flexcontroller left_OuterSquint range 0 1 "left_OuterSquint"
	flexcontroller right_BrowInV range -1 1 "right_BrowInV"
	flexcontroller left_BrowInV range -1 1 "left_BrowInV"
	flexcontroller right_BrowOutV range 0 1 "right_BrowOutV"
	flexcontroller left_BrowOutV range 0 1 "left_BrowOutV"
	flexcontroller right_Frown range 0 1 "right_Frown"
	flexcontroller left_Frown range 0 1 "left_Frown"
	flexcontroller right_NoseV range -1 1 "right_NoseV"
	flexcontroller left_NoseV range -1 1 "left_NoseV"
	flexcontroller right_NostrilFlare range -1 1 "right_NostrilFlare"
	flexcontroller left_NostrilFlare range -1 1 "left_NostrilFlare"
	flexcontroller right_CheekV range 0 1 "right_CheekV"
	flexcontroller left_CheekV range 0 1 "left_CheekV"
	flexcontroller right_CheekH range -1 1 "right_CheekH"
	flexcontroller left_CheekH range -1 1 "left_CheekH"
	flexcontroller JawD range -1 1 "JawD"
	flexcontroller JawH range -1 1 "JawH"
	flexcontroller MouthH range -1 1 "MouthH"
	flexcontroller JawV range -1 1 "JawV"
	flexcontroller right_LipsV range -1 1 "right_LipsV"
	flexcontroller left_LipsV range -1 1 "left_LipsV"
	flexcontroller right_LipUpV range -1 1 "right_LipUpV"
	flexcontroller left_LipUpV range -1 1 "left_LipUpV"
	flexcontroller right_LipLoV range -1 1 "right_LipLoV"
	flexcontroller left_LipLoV range -1 1 "left_LipLoV"
	flexcontroller right_Smile range 0 1 "right_Smile"
	flexcontroller left_Smile range 0 1 "left_Smile"
	flexcontroller multi_Smile range -1 1 "multi_Smile"
	flexcontroller right_Platysmus range 0 1 "right_Platysmus"
	flexcontroller left_Platysmus range 0 1 "left_Platysmus"
	flexcontroller right_FoldLipUp range -1 1 "right_FoldLipUp"
	flexcontroller left_FoldLipUp range -1 1 "left_FoldLipUp"
	flexcontroller right_FoldLipLo range -1 1 "right_FoldLipLo"
	flexcontroller left_FoldLipLo range -1 1 "left_FoldLipLo"
	flexcontroller right_PuckerLipUp range 0 1 "right_PuckerLipUp"
	flexcontroller left_PuckerLipUp range 0 1 "left_PuckerLipUp"
	flexcontroller right_PuckerLipLo range 0 1 "right_PuckerLipLo"
	flexcontroller left_PuckerLipLo range 0 1 "left_PuckerLipLo"
	flexcontroller right_LipCnrTwst range 0 1 "right_LipCnrTwst"
	flexcontroller left_LipCnrTwst range 0 1 "left_LipCnrTwst"
	flexcontroller right_Dimple range 0 1 "right_Dimple"
	flexcontroller left_Dimple range 0 1 "left_Dimple"
	flexcontroller right_PuffLipUp range 0 1 "right_PuffLipUp"
	flexcontroller left_PuffLipUp range 0 1 "left_PuffLipUp"
	flexcontroller right_PuffLipLo range 0 1 "right_PuffLipLo"
	flexcontroller left_PuffLipLo range 0 1 "left_PuffLipLo"
	flexcontroller right_ScalpD range -1 1 "right_ScalpD"
	flexcontroller left_ScalpD range -1 1 "left_ScalpD"
	flexcontroller TongueV range 0 1 "TongueV"
	flexcontroller TongueH range -1 1 "TongueH"
	flexcontroller TongueCurl range -1 1 "TongueCurl"
	flexcontroller TongueD range -1 1 "TongueD"
	flexcontroller TongueWidth range -1 1 "TongueWidth"
	flexcontroller TongueFunnel range 0 1 "TongueFunnel"
	flexcontroller NoHead range 0 1 "NoHead"
	flexcontroller CheekySmile range 0 1 "CheekySmile"

	%LongNails = LongNails
	%BlowNostrilL = (min(max(left_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BlowNostrilR = (min(max(right_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutVL = left_BrowOutV
	%BrowOutVR = right_BrowOutV
	%CheekVL = left_CheekV
	%CheekVR = right_CheekV
	%ClenchJaw = (1 - (min(max(JawV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoL = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoR = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpL = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpR = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsL = (((1 - (min(max(left_LipsV + 1, 0), 1))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsR = (((1 - (min(max(right_LipsV + 1, 0), 1))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekL = (1 - (min(max(left_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekR = (1 - (min(max(right_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleL = (left_Dimple * (1 - left_LipCnrTwst)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleR = (right_Dimple * (1 - right_LipCnrTwst)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FrownL = left_Frown
	%FrownR = right_Frown
	%InflateCheekL = (((min(max(left_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InflateCheekR = (((min(max(right_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquintL = left_InnerSquint
	%InnerSquintR = right_InnerSquint
	%JutJaw = (min(max(JawD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipL = (1 - (min(max(left_LipUpV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipR = (1 - (min(max(right_LipUpV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstL = (left_LipCnrTwst * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstR = (right_LipCnrTwst * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw = (min(max(JawV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsL = (((min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsR = (((min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipL = ((min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipR = ((min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipL = ((min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipR = ((min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsL = ((min(max(left_LipsV, 0), 1)) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsR = ((min(max(right_LipsV, 0), 1)) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipL = (min(max(left_LipLoV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipR = (min(max(right_LipLoV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipL = (min(max(left_LipUpV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipR = (min(max(right_LipUpV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OuterSquintL = left_OuterSquint
	%OuterSquintR = right_OuterSquint
	%PlatysmusL = left_Platysmus
	%PlatysmusR = right_Platysmus
	%PressNoseL = (1 - (min(max(left_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PressNoseR = (1 - (min(max(right_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInL = (min(max(left_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInR = (min(max(right_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinL = (1 - (min(max(left_LipLoV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinR = (1 - (min(max(right_LipLoV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackL = (1 - (min(max(left_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackR = (1 - (min(max(right_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardL = (min(max(left_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardR = (min(max(right_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatL = ((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatR = ((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullL = ((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullR = ((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpL = ((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpR = ((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseL = (min(max(left_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseR = (min(max(right_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckJaw = (1 - (min(max(JawD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLiploL = ((1 - (min(max(left_FoldLipLo + 1, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLiploR = ((1 - (min(max(right_FoldLipLo + 1, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpL = (((1 - (min(max(left_FoldLipUp + 1, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpR = (((1 - (min(max(right_FoldLipUp + 1, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilL = (1 - (min(max(left_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilR = (1 - (min(max(right_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseL = (1 - (min(max(left_BrowInV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseR = (1 - (min(max(right_BrowInV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpL = (left_PuckerLipUp * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpR = (right_PuckerLipUp * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoL = (left_PuckerLipLo * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoR = (right_PuckerLipLo * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpL = ((((min(max(left_FoldLipUp, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpR = ((((min(max(right_FoldLipUp, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoL = ((((min(max(left_FoldLipLo, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoR = ((((min(max(right_FoldLipLo, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpL = (((((left_PuffLipUp * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpR = (((((right_PuffLipUp * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoL = (((((left_PuffLipLo * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoR = (((((right_PuffLipLo * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawL = (min(max(JawH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawR = (1 - (min(max(JawH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack = (1 - (min(max(TongueD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlDown = (1 - (min(max(TongueCurl + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp = (min(max(TongueCurl, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueFunnel = TongueFunnel
	%TongueLeft = (1 - (min(max(TongueH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueNarrow = (1 - (min(max(TongueWidth + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueOut = (min(max(TongueD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueRight = (min(max(TongueH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueV = TongueV
	%TongueWide = (min(max(TongueWidth, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%NoHead = NoHead
	%CheekySmile = CheekySmile
}
$bodygroup "PosterGirl_Clothes"
{
	studio "PosterGirl_Clothes.smd"
}
$model "PosterGirl_Head" "PosterGirl_Head.smd" {

	eyeball "eye_right" "bip_head" -1.470000 -3.340002 75.204107 "eyeball_r" 1 4 "iris_unused" 1
	eyeball "eye_left" "bip_head" 1.470000 -3.340002 75.204107 "eyeball_l" 1 -4 "iris_unused" 1


	flexfile "calendar_girl_feet_04.vta" 
	{
		defaultflex frame 0
		flexpair "BlowNostril" 1 frame 1
		flexpair "BrowOutV" 1 frame 2
		flexpair "CheekV" 1 frame 3
		flex "ClenchJaw" frame 4
		flexpair "CloseLidLo" 1 frame 5
		flexpair "CloseLidUp" 1 frame 6
		flexpair "CompressLips" 1 frame 7
		flexpair "DeflateCheek" 1 frame 8
		flexpair "Dimple" 1 frame 9
		flexpair "Frown" 1 frame 10
		flexpair "InflateCheek" 1 frame 11
		flexpair "InnerSquint" 1 frame 12
		flex "JutJaw" frame 13
		flexpair "JutUpperLip" 1 frame 14
		flexpair "LipCnrTwst" 1 frame 15
		flex "OpenJaw" frame 16
		flexpair "OpenJaw_OpenLips" 1 frame 17
		flexpair "OpenJaw_OpenLowerLip" 1 frame 18
		flexpair "OpenJaw_OpenUpperLip" 1 frame 19
		flexpair "OpenJaw_OpenLowerLip_SmileFlat" 1 frame 20
		flexpair "OpenJaw_OpenUpperLip_SmileFlat" 1 frame 21
		flexpair "OpenJaw_OpenLowerLip_SmileFull" 1 frame 22
		flexpair "OpenJaw_OpenUpperLip_SmileFull" 1 frame 23
		flexpair "OpenJaw_OpenLowerLip_SmileSharp" 1 frame 24
		flexpair "OpenJaw_OpenUpperLip_SmileSharp" 1 frame 25
		flexpair "OpenLips" 1 frame 26
		flexpair "OpenLowerLip" 1 frame 27
		flexpair "OpenUpperLip" 1 frame 28
		flexpair "OuterSquint" 1 frame 29
		flexpair "Platysmus" 1 frame 30
		flexpair "PressNose" 1 frame 31
		flexpair "RaiseBrowIn" 1 frame 32
		flexpair "RaiseChin" 1 frame 33
		flexpair "ScalpBack" 1 frame 34
		flexpair "ScalpForward" 1 frame 35
		flexpair "SmileFlat" 1 frame 36
		flexpair "OpenLowerLip_SmileFlat" 1 frame 37
		flexpair "OpenUpperLip_SmileFlat" 1 frame 38
		flexpair "SmileFull" 1 frame 39
		flexpair "OpenLowerLip_SmileFull" 1 frame 40
		flexpair "OpenUpperLip_SmileFull" 1 frame 41
		flexpair "SmileSharp" 1 frame 42
		flexpair "OpenLowerLip_SmileSharp" 1 frame 43
		flexpair "OpenUpperLip_SmileSharp" 1 frame 44
		flexpair "SneerNose" 1 frame 45
		flex "SuckJaw" frame 46
		flexpair "SuckLiplo" 1 frame 47
		flexpair "SuckLipUp" 1 frame 48
		flexpair "SuckNostril" 1 frame 49
		flexpair "WrinkleNose" 1 frame 50
		flexpair "PuckerLipUp" 1 frame 51
		flexpair "PuckerLipLo" 1 frame 52
		flexpair "FunnelLipUp" 1 frame 53
		flexpair "FunnelLipLo" 1 frame 54
		flexpair "PuffLipUp" 1 frame 55
		flexpair "PuffLipLo" 1 frame 56
		flex "SlideJawL" frame 57
		flex "SlideJawR" frame 58
		flex "NoHead" frame 59
		flex "CheekySmile" frame 60
		flex "TongueBack" frame 61
		flex "TongueCurlDown" frame 62
		flex "TongueCurlUp" frame 63
		flex "TongueFunnel" frame 64
		flex "TongueLeft" frame 65
		flex "TongueNarrow" frame 66
		flex "TongueOut" frame 67
		flex "TongueRight" frame 68
		flex "TongueV" frame 69
		flex "TongueWide" frame 70
	}

	flexcontroller LongNails range 0 1 "LongNails"
	flexcontroller right_CloseLid range -1 1 "right_CloseLid"
	flexcontroller left_CloseLid range -1 1 "left_CloseLid"
	flexcontroller multi_CloseLid range -1 1 "multi_CloseLid"
	flexcontroller blink range 0 1 "blink"
	flexcontroller right_InnerSquint range 0 1 "right_InnerSquint"
	flexcontroller left_InnerSquint range 0 1 "left_InnerSquint"
	flexcontroller right_OuterSquint range 0 1 "right_OuterSquint"
	flexcontroller left_OuterSquint range 0 1 "left_OuterSquint"
	flexcontroller right_BrowInV range -1 1 "right_BrowInV"
	flexcontroller left_BrowInV range -1 1 "left_BrowInV"
	flexcontroller right_BrowOutV range 0 1 "right_BrowOutV"
	flexcontroller left_BrowOutV range 0 1 "left_BrowOutV"
	flexcontroller right_Frown range 0 1 "right_Frown"
	flexcontroller left_Frown range 0 1 "left_Frown"
	flexcontroller right_NoseV range -1 1 "right_NoseV"
	flexcontroller left_NoseV range -1 1 "left_NoseV"
	flexcontroller right_NostrilFlare range -1 1 "right_NostrilFlare"
	flexcontroller left_NostrilFlare range -1 1 "left_NostrilFlare"
	flexcontroller right_CheekV range 0 1 "right_CheekV"
	flexcontroller left_CheekV range 0 1 "left_CheekV"
	flexcontroller right_CheekH range -1 1 "right_CheekH"
	flexcontroller left_CheekH range -1 1 "left_CheekH"
	flexcontroller JawD range -1 1 "JawD"
	flexcontroller JawH range -1 1 "JawH"
	flexcontroller MouthH range -1 1 "MouthH"
	flexcontroller JawV range -1 1 "JawV"
	flexcontroller right_LipsV range -1 1 "right_LipsV"
	flexcontroller left_LipsV range -1 1 "left_LipsV"
	flexcontroller right_LipUpV range -1 1 "right_LipUpV"
	flexcontroller left_LipUpV range -1 1 "left_LipUpV"
	flexcontroller right_LipLoV range -1 1 "right_LipLoV"
	flexcontroller left_LipLoV range -1 1 "left_LipLoV"
	flexcontroller right_Smile range 0 1 "right_Smile"
	flexcontroller left_Smile range 0 1 "left_Smile"
	flexcontroller multi_Smile range -1 1 "multi_Smile"
	flexcontroller right_Platysmus range 0 1 "right_Platysmus"
	flexcontroller left_Platysmus range 0 1 "left_Platysmus"
	flexcontroller right_FoldLipUp range -1 1 "right_FoldLipUp"
	flexcontroller left_FoldLipUp range -1 1 "left_FoldLipUp"
	flexcontroller right_FoldLipLo range -1 1 "right_FoldLipLo"
	flexcontroller left_FoldLipLo range -1 1 "left_FoldLipLo"
	flexcontroller right_PuckerLipUp range 0 1 "right_PuckerLipUp"
	flexcontroller left_PuckerLipUp range 0 1 "left_PuckerLipUp"
	flexcontroller right_PuckerLipLo range 0 1 "right_PuckerLipLo"
	flexcontroller left_PuckerLipLo range 0 1 "left_PuckerLipLo"
	flexcontroller right_LipCnrTwst range 0 1 "right_LipCnrTwst"
	flexcontroller left_LipCnrTwst range 0 1 "left_LipCnrTwst"
	flexcontroller right_Dimple range 0 1 "right_Dimple"
	flexcontroller left_Dimple range 0 1 "left_Dimple"
	flexcontroller right_PuffLipUp range 0 1 "right_PuffLipUp"
	flexcontroller left_PuffLipUp range 0 1 "left_PuffLipUp"
	flexcontroller right_PuffLipLo range 0 1 "right_PuffLipLo"
	flexcontroller left_PuffLipLo range 0 1 "left_PuffLipLo"
	flexcontroller right_ScalpD range -1 1 "right_ScalpD"
	flexcontroller left_ScalpD range -1 1 "left_ScalpD"
	flexcontroller TongueV range 0 1 "TongueV"
	flexcontroller TongueH range -1 1 "TongueH"
	flexcontroller TongueCurl range -1 1 "TongueCurl"
	flexcontroller TongueD range -1 1 "TongueD"
	flexcontroller TongueWidth range -1 1 "TongueWidth"
	flexcontroller TongueFunnel range 0 1 "TongueFunnel"
	flexcontroller NoHead range 0 1 "NoHead"
	flexcontroller CheekySmile range 0 1 "CheekySmile"
	flexcontroller eyes range -30 30 "eyes_updown"
	flexcontroller eyes range -30 30 "eyes_rightleft"

	%LongNails = LongNails
	%BlowNostrilL = (min(max(left_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BlowNostrilR = (min(max(right_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutVL = left_BrowOutV
	%BrowOutVR = right_BrowOutV
	%CheekVL = left_CheekV
	%CheekVR = right_CheekV
	%ClenchJaw = (1 - (min(max(JawV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoL = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoR = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpL = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpR = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -30) / (30 - -30), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsL = (((1 - (min(max(left_LipsV + 1, 0), 1))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsR = (((1 - (min(max(right_LipsV + 1, 0), 1))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekL = (1 - (min(max(left_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekR = (1 - (min(max(right_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleL = (left_Dimple * (1 - left_LipCnrTwst)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleR = (right_Dimple * (1 - right_LipCnrTwst)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FrownL = left_Frown
	%FrownR = right_Frown
	%InflateCheekL = (((min(max(left_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InflateCheekR = (((min(max(right_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquintL = left_InnerSquint
	%InnerSquintR = right_InnerSquint
	%JutJaw = (min(max(JawD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipL = (1 - (min(max(left_LipUpV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipR = (1 - (min(max(right_LipUpV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstL = (left_LipCnrTwst * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstR = (right_LipCnrTwst * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw = (min(max(JawV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsL = (((min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsR = (((min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipL = ((min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipR = ((min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipL = ((min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipR = ((min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsL = ((min(max(left_LipsV, 0), 1)) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsR = ((min(max(right_LipsV, 0), 1)) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipL = (min(max(left_LipLoV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipR = (min(max(right_LipLoV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipL = (min(max(left_LipUpV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipR = (min(max(right_LipUpV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OuterSquintL = left_OuterSquint
	%OuterSquintR = right_OuterSquint
	%PlatysmusL = left_Platysmus
	%PlatysmusR = right_Platysmus
	%PressNoseL = (1 - (min(max(left_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PressNoseR = (1 - (min(max(right_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInL = (min(max(left_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInR = (min(max(right_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinL = (1 - (min(max(left_LipLoV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinR = (1 - (min(max(right_LipLoV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackL = (1 - (min(max(left_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackR = (1 - (min(max(right_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardL = (min(max(left_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardR = (min(max(right_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatL = ((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatR = ((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFlatL = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFlatR = (((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullL = ((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullR = ((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullL = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullR = (((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpL = ((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpR = ((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileSharpL = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileSharpR = (((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseL = (min(max(left_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseR = (min(max(right_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckJaw = (1 - (min(max(JawD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLiploL = ((1 - (min(max(left_FoldLipLo + 1, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLiploR = ((1 - (min(max(right_FoldLipLo + 1, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpL = (((1 - (min(max(left_FoldLipUp + 1, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpR = (((1 - (min(max(right_FoldLipUp + 1, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilL = (1 - (min(max(left_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilR = (1 - (min(max(right_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseL = (1 - (min(max(left_BrowInV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseR = (1 - (min(max(right_BrowInV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpL = (left_PuckerLipUp * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpR = (right_PuckerLipUp * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoL = (left_PuckerLipLo * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoR = (right_PuckerLipLo * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpL = ((((min(max(left_FoldLipUp, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpR = ((((min(max(right_FoldLipUp, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoL = ((((min(max(left_FoldLipLo, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoR = ((((min(max(right_FoldLipLo, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpL = (((((left_PuffLipUp * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpR = (((((right_PuffLipUp * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoL = (((((left_PuffLipLo * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoR = (((((right_PuffLipLo * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawL = (min(max(JawH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawR = (1 - (min(max(JawH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack = (1 - (min(max(TongueD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlDown = (1 - (min(max(TongueCurl + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp = (min(max(TongueCurl, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueFunnel = TongueFunnel
	%TongueLeft = (1 - (min(max(TongueH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueNarrow = (1 - (min(max(TongueWidth + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueOut = (min(max(TongueD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueRight = (min(max(TongueH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueV = TongueV
	%TongueWide = (min(max(TongueWidth, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%NoHead = NoHead
	%CheekySmile = CheekySmile
}


$surfaceprop "flesh"

$contents "solid"

$illumposition 0 -1.178 39.451

$mostlyopaque

$cdmaterials "models\build_your_human\hwm\calendar_girl\"
$cdmaterials ""

$attachment "eyes" "bip_head" 0 -3.6 -3.03 rotate 80.54 -90 0
$attachment "mouth" "bip_head" 0.8 -5.8 -0.15 rotate 0 -80 -90

$cbox 0 0 0 0 0 0

$bbox -9.973 -25.045 -4.021 12.329 25.045 82.923

$definebone "bip_pelvis" "" 0 1.710891 45.858799 0.000001 -0.000014 -84.271332 0 0 0 0 0 0
$definebone "bip_spine_0" "bip_pelvis" 0 -5.447147 -0.004592 -0.000014 0 -2.913724 0 0 0 0 0 0
$definebone "bip_spine_1" "bip_spine_0" 0 -4.490498 -0.021385 -0.000057 0 -11.35223 0 0 0 0 0 0
$definebone "bip_spine_2" "bip_spine_1" 0 -5.060825 0.000031 0 0 14.196377 0 0 0 0 0 0
$definebone "bip_spine_3" "bip_spine_2" 0 -5.603661 -0.000011 0 0 24.326543 0 0 0 0 0 0
$definebone "bip_neck" "bip_spine_3" 0 -2.055744 0.514782 0 0 -12.465273 0 0 0 0 0 0
$definebone "bip_head" "bip_neck" 0 -3.947258 0.031963 0.000057 0 -8.056002 0 0 0 0 0 0
$definebone "bip_hair1" "bip_head" 3.628415 -5.246796 -1.637892 6.559422 -17.28731 2.577847 0 0 0 0 0 0
$definebone "bip_hair2" "bip_head" 4.274755 -2.189621 2.422182 15.546144 -8.673444 -7.00494 0 0 0 0 0 0
$definebone "bip_hair3" "bip_head" -0.000001 -1.666229 5.561819 16.131117 -0.641701 -2.308428 0 0 0 0 0 0
$definebone "bip_hair4" "bip_head" -4.274757 -2.189621 2.422183 17.136376 4.696651 -7.062473 0 0 0 0 0 0
$definebone "bip_hair5" "bip_head" -3.739575 -2.725494 -0.792352 15.322862 -4.651548 -10.504296 0 0 0 0 0 0
$definebone "bip_collar_L" "bip_spine_3" 1.146524 -1.131268 -2.359467 -27.690589 -71.74486 -173.540914 0 0 0 0 0 0
$definebone "bip_upperArm_L" "bip_collar_L" 0.092571 -5.807673 -1.37315 -5.416139 -14.265432 -16.397285 0 0 0 0 0 0
$definebone "bip_lowerArm_L" "bip_upperArm_L" -0.026993 -9.811298 -0.00868 4.17086 8.034078 -45.425081 0 0 0 0 0 0
$definebone "bip_hand_L" "bip_lowerArm_L" -0.050598 -9.756442 0.031833 30.643422 4.310135 -1.375796 0 0 0 0 0 0
$definebone "bip_thumb_0_L" "bip_hand_L" -0.892887 -1.003657 0.908257 -15.373832 -27.333543 -17.730015 0 0 0 0 0 0
$definebone "bip_thumb_1_L" "bip_thumb_0_L" 0.035839 -1.877951 0.070992 7.611192 3.389403 11.859256 0 0 0 0 0 0
$definebone "bip_thumb_2_L" "bip_thumb_1_L" 0.019409 -1.823948 -0.033466 3.516615 -2.162129 18.83918 0 0 0 0 0 0
$definebone "bip_index_0_L" "bip_hand_L" -0.126446 -3.985683 0.893555 77.584966 64.154929 83.696995 0 0 0 0 0 0
$definebone "bip_index_1_L" "bip_index_0_L" -0.047985 -1.94163 -0.019081 -1.630815 7.05889 36.417517 0 0 0 0 0 0
$definebone "bip_index_2_L" "bip_index_1_L" 0.011635 -1.224533 0.096321 -0.256457 0.979326 10.012625 0 0 0 0 0 0
$definebone "bip_middle_0_L" "bip_hand_L" 0.141972 -3.749284 -0.080814 72.771779 92.644727 117.325233 0 0 0 0 0 0
$definebone "bip_middle_1_L" "bip_middle_0_L" -0.010899 -2.414082 0.085388 -1.892645 6.619751 36.175957 0 0 0 0 0 0
$definebone "bip_middle_2_L" "bip_middle_1_L" -0.015862 -1.414997 0.077765 -0.346341 0.965508 21.003498 0 0 0 0 0 0
$definebone "bip_ring_0_L" "bip_hand_L" 0.133446 -3.451468 -0.979843 68.500821 93.395993 116.388992 0 0 0 0 0 0
$definebone "bip_ring_1_L" "bip_ring_0_L" -0.000023 -2.022123 0.00005 -0.104771 0.102295 36.981929 0 0 0 0 0 0
$definebone "bip_ring_2_L" "bip_ring_1_L" 0.019493 -1.330826 0.08552 0.015322 0.615542 18.020558 0 0 0 0 0 0
$definebone "bip_pinky_0_L" "bip_hand_L" -0.009113 -3.076676 -1.953865 64.424585 100.318998 125.535489 0 0 0 0 0 0
$definebone "bip_pinky_1_L" "bip_pinky_0_L" 0.009491 -1.654938 0.099201 -0.000891 0.000737 29.376254 0 0 0 0 0 0
$definebone "bip_pinky_2_L" "bip_pinky_1_L" -0.047707 -1.18272 -0.069014 0.000362 -0.002878 18.107409 0 0 0 0 0 0
$definebone "hlp_forearm_L" "bip_lowerArm_L" 0.000267 -4.757792 0.000039 -0.000287 0.00493 -0.001656 0 0 0 0 0 0
$definebone "bip_bicep_twist_01_L" "bip_upperArm_L" -0.112705 -3.54615 -0.065885 0.000901 0.004313 0.000268 0 0 0 0 0 0
$definebone "bip_bicep_twist_02_L" "bip_upperArm_L" -0.007164 -6.885904 -0.013637 0.001104 0.008314 0.000239 0 0 0 0 0 0
$definebone "bip_collar_R" "bip_spine_3" -1.146525 -1.131298 -2.359446 27.689389 71.744362 6.458317 0 0 0 0 0 0
$definebone "bip_upperArm_R" "bip_collar_R" -0.092567 5.807663 1.373192 -5.411218 -14.257322 -16.397503 0 0 0 0 0 0
$definebone "bip_lowerArm_R" "bip_upperArm_R" 0.028542 9.811359 0.008603 4.16878 8.0272 -45.425317 0 0 0 0 0 0
$definebone "bip_hand_R" "bip_lowerArm_R" 0.050694 9.756417 -0.031888 30.6453 4.309014 -1.376091 0 0 0 0 0 0
$definebone "bip_thumb_0_R" "bip_hand_R" 0.892868 1.003726 -0.908237 -15.373123 -27.33327 -17.729674 0 0 0 0 0 0
$definebone "bip_thumb_1_R" "bip_thumb_0_R" -0.035767 1.877964 -0.071007 7.61016 3.389391 11.859059 0 0 0 0 0 0
$definebone "bip_thumb_2_R" "bip_thumb_1_R" -0.019501 1.823882 0.033489 3.516935 -2.162108 18.839156 0 0 0 0 0 0
$definebone "bip_index_0_R" "bip_hand_R" 0.126442 3.985715 -0.893543 77.583326 64.155748 83.702425 0 0 0 0 0 0
$definebone "bip_index_1_R" "bip_index_0_R" 0.048038 1.941579 0.018871 -1.629996 7.057628 36.412418 0 0 0 0 0 0
$definebone "bip_index_2_R" "bip_index_1_R" -0.011639 1.224602 -0.096313 -0.257096 0.979214 10.012578 0 0 0 0 0 0
$definebone "bip_middle_0_R" "bip_hand_R" -0.142021 3.749305 0.080818 72.772981 92.643791 117.323853 0 0 0 0 0 0
$definebone "bip_middle_1_R" "bip_middle_0_R" 0.01086 2.414103 -0.085419 -1.891096 6.621303 36.176128 0 0 0 0 0 0
$definebone "bip_middle_2_R" "bip_middle_1_R" 0.015858 1.414986 -0.077724 -0.346504 0.965687 21.003334 0 0 0 0 0 0
$definebone "bip_ring_0_R" "bip_hand_R" -0.133503 3.451501 0.979851 68.500527 93.398582 116.390795 0 0 0 0 0 0
$definebone "bip_ring_1_R" "bip_ring_0_R" 0.000031 2.022068 -0.000042 -0.107324 0.102882 36.979648 0 0 0 0 0 0
$definebone "bip_ring_2_R" "bip_ring_1_R" -0.019489 1.330868 -0.085459 0.01551 0.618089 18.022018 0 0 0 0 0 0
$definebone "bip_pinky_0_R" "bip_hand_R" 0.009045 3.076744 1.95388 64.424236 100.319954 125.533782 0 0 0 0 0 0
$definebone "bip_pinky_1_R" "bip_pinky_0_R" -0.009502 1.654911 -0.099094 -0.001134 0.000694 29.378314 0 0 0 0 0 0
$definebone "bip_pinky_2_R" "bip_pinky_1_R" 0.04771 1.182697 0.06905 -0.000658 -0.001994 18.105539 0 0 0 0 0 0
$definebone "hlp_forearm_R" "bip_lowerArm_R" -0.000225 4.757782 -0.000064 0.000031 -0.000157 0.000041 0 0 0 0 0 0
$definebone "bip_bicep_twist_01_R" "bip_upperArm_R" 0.113235 3.546127 0.065864 -0.000358 -0.004165 -0.000224 0 0 0 0 0 0
$definebone "bip_bicep_twist_02_R" "bip_upperArm_R" -0.056137 6.885914 0.016321 -0.000836 -0.004621 -0.000243 0 0 0 0 0 0
$definebone "bip_boob_L" "bip_spine_2" 3.201013 0.589993 -5.863968 -22.869586 -22.490085 -86.447614 0 0 0 0 0 0
$definebone "bip_boob_R" "bip_spine_2" -3.201022 0.589993 -5.863961 18.174167 -26.360955 -104.55502 0 0 0 0 0 0
$definebone "bip_hip_L" "bip_pelvis" 4.234444 2.704231 -1.270597 -12.724911 1.690336 178.899183 0 0 0 0 0 0
$definebone "bip_knee_L" "bip_hip_L" -0.796832 -18.032427 -0.389708 -0.871726 -1.455033 -2.895717 0 0 0 0 0 0
$definebone "bip_foot_L" "bip_knee_L" 0.48106 -21.107546 -0.483502 2.754346 -0.980513 -53.488957 0 0 0 0 0 0
$definebone "bip_toe_L" "bip_foot_L" 0.301238 -6.769624 1.598212 1.115205 1.851641 -35.827375 0 0 0 0 0 0
$definebone "bip_hip_R" "bip_pelvis" -4.234434 2.704277 -1.270587 12.724501 -1.690214 -1.100332 0 0 0 0 0 0
$definebone "bip_knee_R" "bip_hip_R" 0.796874 18.032391 0.389583 -0.871811 -1.455484 -2.89618 0 0 0 0 0 0
$definebone "bip_foot_R" "bip_knee_R" -0.481093 21.107508 0.483572 2.756173 -0.982437 -53.487905 0 0 0 0 0 0
$definebone "bip_toe_R" "bip_foot_R" -0.301229 6.769588 -1.598364 1.116491 1.849471 -35.828645 0 0 0 0 0 0

$proceduralbones "calendar_girl_feet.vrd"


$sequence "ragdoll" {
	"calendar_girl_feet_anims\ragdoll.smd"
	activity "idle" 1
	fadein 0.2
	fadeout 0.2
	fps 30
}
